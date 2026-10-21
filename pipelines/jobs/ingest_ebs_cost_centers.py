"""Glue job: Oracle EBS cost center extract -> FDP_MDM.LANDING.COST_CENTER_RAW.

Local run: python -m pipelines.jobs.ingest_ebs_cost_centers --input data/samples/ebs_cost_centers_extract.csv
"""

from __future__ import annotations

import argparse
import os
from datetime import UTC, datetime

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

from pipelines.framework import expectations
from pipelines.framework.sources import load_source
from pipelines.framework.spark import get_spark
from pipelines.warehouse.base import Warehouse, get_warehouse

CC_WIDTH = int(os.environ.get("COST_CENTER_CODE_WIDTH", "6"))


def transform(raw: DataFrame, run_id: str) -> DataFrame:
    contract = load_source("ebs_cost_centers")
    df = raw.select([F.col(src).alias(dst) for src, dst in contract.columns.items()])
    df = (
        df.withColumn("entity_code", F.upper(F.trim("entity_code")))
        # EBS stores segment2 unpadded for the older ledgers; the MDM key is always CC_WIDTH digits.
        .withColumn("cost_center_code", F.lpad(F.trim("cost_center_code"), CC_WIDTH, "0"))
        .withColumn(
            "parent_cost_center_code",
            F.when(F.trim("parent_cost_center_code") == "", None).otherwise(F.lpad(F.trim("parent_cost_center_code"), CC_WIDTH, "0")),
        )
        .withColumn("description", F.substring(F.trim("description"), 1, 120))
        .withColumn("status", F.when(F.col("status") == "Y", "ACTIVE").otherwise("RETIRED"))
        .withColumn("source_system", F.lit("EBS"))
        .withColumn("publish_run_id", F.lit(run_id))
    )
    return df


def run(spark: SparkSession, input_path: str, warehouse: Warehouse, run_id: str | None = None) -> int:
    contract = load_source("ebs_cost_centers")
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    raw = spark.read.options(**{k: str(v) for k, v in contract.options.items()}).csv(input_path)
    df = transform(raw, run_id)
    expectations.enforce(df, contract.expectations)
    return warehouse.load_dataframe(df.toPandas(), contract.target_table)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    args = ap.parse_args()
    n = run(get_spark("ingest_ebs_cost_centers"), args.input, get_warehouse())
    print(f"loaded {n} cost centers")
