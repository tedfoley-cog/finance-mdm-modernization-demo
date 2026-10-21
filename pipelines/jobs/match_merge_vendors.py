"""Glue job: group LANDING.VENDOR_RAW rows into golden records and write CURATED.VENDOR_MATCH_GROUPS.

Match rule 1 (TAX_ID): identical normalised tax id within a country.
Match rule 2 (NAME_CC): identical simplified legal name + default cost center (fallback when no tax id).
Survivorship: SAP wins over EBS; otherwise the lowest vendor_id survives.
"""

from __future__ import annotations

import argparse
import uuid
from datetime import UTC, datetime

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T
from pyspark.sql.window import Window

from pipelines.framework.spark import get_spark
from pipelines.warehouse.base import Warehouse, get_warehouse


@F.udf(returnType=T.StringType())
def normalize_tax_id(raw: str | None) -> str | None:
    """Strip hyphens and upper-case (SAP STCD1 convention)."""
    if raw is None:
        return None
    value = raw.replace("-", "").upper()
    return value or None


@F.udf(returnType=T.StringType())
def golden_id(match_key: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"ledgercore-mdm/vendor/{match_key}"))


def build_match_groups(vendors: DataFrame, run_id: str) -> DataFrame:
    df = vendors.withColumn("tax_norm", normalize_tax_id(F.col("tax_id")))
    df = df.withColumn("name_simple", F.upper(F.regexp_replace(F.col("legal_name"), r"[^A-Za-z0-9]", "")))
    df = df.withColumn(
        "match_key",
        F.when(F.col("tax_norm").isNotNull(), F.concat_ws(":", F.lit("TAX"), F.col("country_code"), F.col("tax_norm"))).otherwise(
            F.concat_ws(":", F.lit("NAME_CC"), F.col("name_simple"), F.col("default_cost_center_code"))
        ),
    ).withColumn("match_rule", F.when(F.col("tax_norm").isNotNull(), "TAX_ID").otherwise("NAME_CC"))

    rank = Window.partitionBy("match_key").orderBy(F.when(F.col("source_system") == "SAP", 0).otherwise(1), F.col("vendor_id"))
    return (
        df.withColumn("survivor_flag", F.row_number().over(rank) == 1)
        .withColumn("golden_record_id", golden_id(F.col("match_key")))
        .withColumn("run_id", F.lit(run_id))
        .select(
            "golden_record_id",
            "vendor_id",
            "match_key",
            "match_rule",
            "survivor_flag",
            "run_id",
            F.col("tax_norm").alias("tax_id_normalized"),
        )
    )


def run(spark: SparkSession, warehouse: Warehouse, run_id: str | None = None) -> int:
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    landed = warehouse.query(
        "SELECT VENDOR_ID, LEGAL_NAME, TAX_ID, COUNTRY_CODE, DEFAULT_COST_CENTER_CODE, SOURCE_SYSTEM FROM FDP_MDM.LANDING.VENDOR_RAW"
    )
    landed.columns = [c.lower() for c in landed.columns]
    vendors = spark.createDataFrame(landed)
    groups = build_match_groups(vendors, run_id).toPandas()
    n = warehouse.load_dataframe(
        groups[["golden_record_id", "vendor_id", "match_key", "match_rule", "survivor_flag", "run_id"]],
        "FDP_MDM.CURATED.VENDOR_MATCH_GROUPS",
        mode="overwrite",
    )
    warehouse.execute(
        "MERGE INTO FDP_MDM.CURATED.DIM_VENDOR t USING ("
        " SELECT r.VENDOR_ID, g.GOLDEN_RECORD_ID, r.LEGAL_NAME, r.TAX_ID, r.COUNTRY_CODE, r.PAYMENT_TERMS,"
        "        r.DEFAULT_COST_CENTER_CODE, r.STATUS, r.SOURCE_SYSTEM"
        " FROM FDP_MDM.LANDING.VENDOR_RAW r JOIN FDP_MDM.CURATED.VENDOR_MATCH_GROUPS g ON g.VENDOR_ID = r.VENDOR_ID"
        f" WHERE g.RUN_ID = '{run_id}') s ON t.VENDOR_ID = s.VENDOR_ID"
        " WHEN MATCHED THEN UPDATE SET GOLDEN_RECORD_ID = s.GOLDEN_RECORD_ID, LEGAL_NAME = s.LEGAL_NAME,"
        "   TAX_ID_NORMALIZED = FDP_MDM.UTIL.FN_NORMALIZE_TAX_ID(s.TAX_ID), COUNTRY_CODE = s.COUNTRY_CODE,"
        "   PAYMENT_TERMS = s.PAYMENT_TERMS, DEFAULT_COST_CENTER_CODE = s.DEFAULT_COST_CENTER_CODE,"
        "   STATUS = s.STATUS, SOURCE_SYSTEM = s.SOURCE_SYSTEM, UPDATED_AT = CURRENT_TIMESTAMP()"
        " WHEN NOT MATCHED THEN INSERT (VENDOR_ID, GOLDEN_RECORD_ID, LEGAL_NAME, TAX_ID_NORMALIZED, COUNTRY_CODE,"
        "   PAYMENT_TERMS, DEFAULT_COST_CENTER_CODE, STATUS, SOURCE_SYSTEM, UPDATED_AT)"
        " VALUES (s.VENDOR_ID, s.GOLDEN_RECORD_ID, s.LEGAL_NAME, FDP_MDM.UTIL.FN_NORMALIZE_TAX_ID(s.TAX_ID),"
        "   s.COUNTRY_CODE, s.PAYMENT_TERMS, s.DEFAULT_COST_CENTER_CODE, s.STATUS, s.SOURCE_SYSTEM, CURRENT_TIMESTAMP())"
    )
    return n


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--duckdb-path", default="pipelines/.local/fdp_mdm.duckdb")
    args = ap.parse_args()
    print(f"matched {run(get_spark('match_merge_vendors'), get_warehouse(path=args.duckdb_path))} vendors")
