"""Glue job: SAP LFA1 vendor extract -> FDP_MDM.LANDING.VENDOR_RAW.

Local run: python -m pipelines.jobs.ingest_sap_vendors --input data/samples/sap_lfa1_extract.psv
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from pipelines.framework import expectations
from pipelines.framework.sources import load_source
from pipelines.framework.spark import get_spark
from pipelines.warehouse.base import Warehouse, get_warehouse


def transform(raw: DataFrame, run_id: str) -> DataFrame:
    contract = load_source("sap_vendors")
    df = raw.select([F.col(src).alias(dst) for src, dst in contract.columns.items()])
    return (
        df.withColumn("vendor_id", F.concat(F.lit("V"), F.lpad(F.regexp_replace("vendor_id", "^0+", ""), 7, "0")))
        .withColumn("legal_name", F.substring(F.trim("legal_name"), 1, 200))
        .withColumn("tax_id", F.when(F.trim("tax_id") == "", None).otherwise(F.trim("tax_id")))
        .withColumn("tax_id_normalized", F.lit(None).cast("string"))  # filled by match_merge_vendors
        .withColumn("country_code", F.upper("country_code"))
        .withColumn("payment_terms", F.coalesce(F.col("payment_terms"), F.lit("NET30")))
        .withColumn(
            "default_cost_center_code",
            F.when(F.trim("default_cost_center_code") == "", None).otherwise(F.lpad(F.trim("default_cost_center_code"), 6, "0")),
        )
        # INC-48112: SAP sends LOEVM as 'X' or 'L' (blocked for posting) - both must retire the vendor
        .withColumn("status", F.when(F.col("status").isin("X", "L"), "RETIRED").otherwise("ACTIVE"))
        .withColumn("golden_record_id", F.lit(None).cast("string"))
        .withColumn("source_system", F.lit("SAP"))
        .withColumn("publish_run_id", F.lit(run_id))
    )


def run(spark: SparkSession, input_path: str, warehouse: Warehouse, run_id: str | None = None) -> int:
    contract = load_source("sap_vendors")
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    raw = spark.read.options(**{k: str(v) for k, v in contract.options.items()}).csv(input_path)
    df = transform(raw, run_id)
    expectations.enforce(df, contract.expectations)
    return warehouse.load_dataframe(df.toPandas(), contract.target_table)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    args = ap.parse_args()
    n = run(get_spark("ingest_sap_vendors"), args.input, get_warehouse())
    print(f"loaded {n} vendors")
