"""Glue job: treasury house-bank account register -> FDP_MDM.LANDING.BANK_ACCOUNT_RAW.

Local run: python -m pipelines.jobs.ingest_treasury_bank_accounts --input data/samples/treasury_bank_accounts.csv
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime

from pyspark.sql import Column, DataFrame, SparkSession
from pyspark.sql import functions as F

from pipelines.framework import expectations
from pipelines.framework.sources import load_source
from pipelines.framework.spark import get_spark
from pipelines.warehouse.base import Warehouse, get_warehouse

_SEPARATORS = r"[\s\-.]"


def _compact(col: str) -> Column:
    """Drop the spacing/punctuation banks print in account numbers and sort codes; empty -> NULL."""
    v = F.upper(F.regexp_replace(F.col(col), _SEPARATORS, ""))
    return F.when(v == "", None).otherwise(v)


def transform(raw: DataFrame, run_id: str) -> DataFrame:
    contract = load_source("treasury_bank_accounts")
    df = raw.select([F.col(src).alias(dst) for src, dst in contract.columns.items()])
    return (
        df.withColumn("entity_code", F.upper(F.trim("entity_code")))
        .withColumn("bank_name", F.trim("bank_name"))
        .withColumn("swift_bic", F.upper(F.regexp_replace("swift_bic", r"\s", "")))
        .withColumn("routing_code", _compact("routing_code"))
        .withColumn("account_number", _compact("account_number"))
        .withColumn("currency_code", F.upper(F.trim("currency_code")))
        .withColumn("account_purpose", F.upper(F.trim("account_purpose")))
        .withColumn("status", F.upper(F.trim("status")))
        .withColumn("opened_on", F.to_date("opened_on", "yyyy-MM-dd"))
        .withColumn("bank_account_id", F.concat_ws(":", "entity_code", "swift_bic", "account_number"))
        .withColumn("source_system", F.lit("TREASURY"))
        .withColumn("publish_run_id", F.lit(run_id))
    )


def run(spark: SparkSession, input_path: str, warehouse: Warehouse, run_id: str | None = None) -> int:
    contract = load_source("treasury_bank_accounts")
    run_id = run_id or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    raw = spark.read.options(**{k: str(v) for k, v in contract.options.items()}).csv(input_path)
    df = transform(raw, run_id)
    expectations.enforce(df, contract.expectations)
    return warehouse.load_dataframe(df.toPandas(), contract.target_table)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    args = ap.parse_args()
    n = run(get_spark("ingest_treasury_bank_accounts"), args.input, get_warehouse())
    print(f"loaded {n} bank accounts")
