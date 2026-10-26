import json
import re

import duckdb
import pandas as pd
import pytest

from pipelines.tests.conftest import ROOT
from pipelines.warehouse.duckdb_warehouse import DuckDBWarehouse, split_statements

GOLDEN_TAX_IDS = json.loads((ROOT / "data/golden/normalize_tax_id.json").read_text())["vectors"]


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
        " VALUES ('US01', '123456', 'ok', 'ACTIVE', 'EBS')"
    )
    with pytest.raises(duckdb.ConstraintException):
        warehouse.execute(
            "INSERT INTO FDP_MDM.CURATED.DIM_COST_CENTER (ENTITY_CODE, COST_CENTER_CODE, DESCRIPTION, STATUS, SOURCE_SYSTEM)"
            " VALUES ('US01', '1234567890', 'too wide', 'ACTIVE', 'EBS')"
        )


def test_udf_matches_api_normalizer(warehouse):
    from api.app.validators import normalize_tax_id

    for v in GOLDEN_TAX_IDS:
        if v["raw"] is None:
            continue
        got = warehouse.query(f"SELECT FDP_MDM.UTIL.FN_NORMALIZE_TAX_ID('{v['raw']}') AS v")["v"][0]
        got = None if pd.isna(got) else got
        assert got == v["expected"] == normalize_tax_id(v["raw"]), repr(v["raw"])


def test_split_statements_respects_dollar_quotes():
    text = "CREATE OR REPLACE FUNCTION f(x VARCHAR) RETURNS VARCHAR LANGUAGE SQL AS $$ a; b $$; SELECT 1;"
    assert len(split_statements(text)) == 2
