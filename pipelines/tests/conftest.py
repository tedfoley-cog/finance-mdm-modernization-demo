from pathlib import Path

import pytest

from pipelines.framework.spark import get_spark
from pipelines.warehouse.duckdb_warehouse import DuckDBWarehouse

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def spark():
    s = get_spark("ledgercore-tests")
    yield s
    s.stop()


@pytest.fixture
def warehouse():
    wh = DuckDBWarehouse()
    wh.apply_ddl_dir(ROOT / "snowflake" / "sql")
    return wh
