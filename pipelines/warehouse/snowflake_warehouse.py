"""Snowflake implementation. Only imported when MDM_WAREHOUSE=snowflake; credentials come from the
environment (populated from Secrets Manager by the Glue job wrapper)."""

from __future__ import annotations

import os

import pandas as pd

from .base import ApplyResult, Warehouse
from .duckdb_warehouse import split_statements


class SnowflakeWarehouse(Warehouse):
    dialect = "snowflake"

    def __init__(self, **_: object) -> None:
        import snowflake.connector  # noqa: PLC0415

        self.conn = snowflake.connector.connect(
            account=os.environ["SNOWFLAKE_ACCOUNT"],
            user=os.environ["SNOWFLAKE_USER"],
            authenticator=os.environ.get("SNOWFLAKE_AUTHENTICATOR", "oauth"),
            token=os.environ.get("SNOWFLAKE_TOKEN"),
            warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "FDP_TRANSFORM_WH"),
            database="FDP_MDM",
            role=os.environ.get("SNOWFLAKE_ROLE", "FDP_MDM_LOADER"),
        )

    def execute(self, sql: str) -> None:
        self.conn.cursor().execute(sql)

    def query(self, sql: str) -> pd.DataFrame:
        return self.conn.cursor().execute(sql).fetch_pandas_all()

    def load_dataframe(self, df: pd.DataFrame, table: str, mode: str = "append") -> int:
        from snowflake.connector.pandas_tools import write_pandas  # noqa: PLC0415

        database, schema, name = table.split(".")
        if mode == "overwrite":
            self.execute(f"TRUNCATE TABLE {table}")
        _, _, nrows, _ = write_pandas(self.conn, df, name, database=database, schema=schema, quote_identifiers=False)
        return nrows

    def apply_ddl(self, sql_text: str) -> ApplyResult:
        result = ApplyResult()
        for stmt in split_statements(sql_text):
            self.execute(stmt)
            result.applied.append(" ".join(stmt.split()[:4]))
        return result
