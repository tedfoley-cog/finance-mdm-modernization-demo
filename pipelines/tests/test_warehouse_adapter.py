import re

import duckdb
import pytest

from pipelines.tests.conftest import ROOT
from pipelines.warehouse.duckdb_warehouse import DuckDBWarehouse, split_statements


def test_snowflake_ddl_applies_on_duckdb(warehouse):
    for table in [
        "FDP_MDM.LANDING.VENDOR_RAW",
        "FDP_MDM.LANDING.COST_CENTER_RAW",
        "FDP_MDM.CURATED.DIM_COST_CENTER",
        "FDP_MDM.CURATED.DIM_VENDOR",
        "FDP_MDM.CONSUMPTION.VW_VENDOR_GOLDEN",
    ]:
        assert warehouse.table_exists(table), table


def test_skipped_statements_are_only_snowflake_only_constructs():
    wh = DuckDBWarehouse()
    result = wh.apply_ddl_dir(ROOT / "snowflake" / "sql")
    allowed = re.compile(r"^(CREATE (OR REPLACE )?(DATABASE|SCHEMA|STAGE|TASK|PROCEDURE|STORAGE)|COPY INTO|ALTER TASK)", re.I)
    for head, _ in result.skipped:
        assert allowed.match(head), head
    assert len(result.applied) >= 10


def test_varchar_width_is_enforced(warehouse):
    warehouse.execute(
        "INSERT INTO FDP_MDM.CURATED.DIM_COST_CENTER (ENTITY_CODE, COST_CENTER_CODE, DESCRIPTION, STATUS, SOURCE_SYSTEM)"
        " VALUES ('US01', '1234567890', 'ok', 'ACTIVE', 'EBS')"
    )
    with pytest.raises(duckdb.ConstraintException):
        warehouse.execute(
            "INSERT INTO FDP_MDM.CURATED.DIM_COST_CENTER (ENTITY_CODE, COST_CENTER_CODE, DESCRIPTION, STATUS, SOURCE_SYSTEM)"
            " VALUES ('US01', '12345678901', 'too wide', 'ACTIVE', 'EBS')"
        )


def test_ten_char_cost_center_code_loads_into_curated(warehouse):
    # MBA-3472: S/4 codes are 10 digits; landing, curated and the parent column must all take them.
    warehouse.execute(
        "INSERT INTO FDP_MDM.LANDING.COST_CENTER_RAW (ENTITY_CODE, COST_CENTER_CODE, DESCRIPTION, PARENT_COST_CENTER_CODE,"
        " STATUS, PUBLISH_RUN_ID) VALUES ('DE01', '2000001234', 'S/4 cost center', '2000000000', 'ACTIVE', 't-3472')"
    )
    warehouse.execute(
        "INSERT INTO FDP_MDM.CURATED.DIM_COST_CENTER (ENTITY_CODE, COST_CENTER_CODE, DESCRIPTION, PARENT_COST_CENTER_CODE,"
        " STATUS, SOURCE_SYSTEM) SELECT ENTITY_CODE, COST_CENTER_CODE, DESCRIPTION, PARENT_COST_CENTER_CODE, STATUS, 'EBS'"
        " FROM FDP_MDM.LANDING.COST_CENTER_RAW WHERE PUBLISH_RUN_ID = 't-3472'"
    )
    row = warehouse.query(
        "SELECT COST_CENTER_CODE, PARENT_COST_CENTER_CODE FROM FDP_MDM.CURATED.DIM_COST_CENTER WHERE ENTITY_CODE = 'DE01'"
    )
    assert row["COST_CENTER_CODE"][0] == "2000001234"
    assert row["PARENT_COST_CENTER_CODE"][0] == "2000000000"
    assert len(row["COST_CENTER_CODE"][0]) == 10


def test_udf_matches_api_normalizer(warehouse):
    from api.app.validators import normalize_tax_id

    for raw in ["12-3456789", "DE 123 456 789", "12.345.678/0001-90", "gb123456789"]:
        got = warehouse.query(f"SELECT FDP_MDM.UTIL.FN_NORMALIZE_TAX_ID('{raw}') AS v")["v"][0]
        assert got == normalize_tax_id(raw), raw


def test_split_statements_respects_dollar_quotes():
    text = "CREATE OR REPLACE FUNCTION f(x VARCHAR) RETURNS VARCHAR LANGUAGE SQL AS $$ a; b $$; SELECT 1;"
    assert len(split_statements(text)) == 2
