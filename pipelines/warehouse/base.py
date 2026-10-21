"""Warehouse adapter contract. Jobs never import a vendor driver directly; they ask for a Warehouse.

MDM_WAREHOUSE=snowflake  -> SnowflakeWarehouse (snowflake-connector-python, credentials from env/Secrets Manager)
MDM_WAREHOUSE=duckdb     -> DuckDBWarehouse (local file, Snowflake SQL transpiled by sqlglot) - default in tests/CI
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import pandas as pd


@dataclass
class ApplyResult:
    applied: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)  # (statement head, reason)


class Warehouse(ABC):
    dialect: str

    @abstractmethod
    def execute(self, sql: str) -> None: ...

    @abstractmethod
    def query(self, sql: str) -> pd.DataFrame: ...

    @abstractmethod
    def load_dataframe(self, df: pd.DataFrame, table: str, mode: str = "append") -> int: ...

    @abstractmethod
    def apply_ddl(self, sql_text: str) -> ApplyResult: ...

    def table_exists(self, table: str) -> bool:
        try:
            self.query(f"SELECT 1 FROM {table} LIMIT 0")
            return True
        except Exception:
            return False


def get_warehouse(**kwargs) -> Warehouse:
    engine = os.environ.get("MDM_WAREHOUSE", "duckdb").lower()
    if engine == "snowflake":
        from .snowflake_warehouse import SnowflakeWarehouse

        return SnowflakeWarehouse(**kwargs)
    from .duckdb_warehouse import DuckDBWarehouse

    return DuckDBWarehouse(**kwargs)
