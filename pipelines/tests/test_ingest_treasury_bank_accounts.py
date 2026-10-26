import re

import pandas as pd
import pytest

from pipelines.framework.expectations import ExpectationError
from pipelines.jobs import ingest_treasury_bank_accounts
from pipelines.tests.conftest import ROOT

SAMPLE = ROOT / "data" / "samples" / "treasury_bank_accounts.csv"
HEADER = "ENTITY,BANK_NAME,SWIFT_BIC,ROUTING_OR_SORT,ACCOUNT_NUMBER,CURRENCY,ACCOUNT_PURPOSE,STATUS,OPENED_ON\n"


def _sp_load_bank_accounts_merge(run_id: str) -> str:
    """The MERGE inside UTIL.SP_LOAD_BANK_ACCOUNTS (procedures are skipped on DuckDB, so run its body)."""
    text = (ROOT / "snowflake/sql/030_tasks.sql").read_text()
    proc = text.split("PROCEDURE FDP_MDM.UTIL.SP_LOAD_BANK_ACCOUNTS", 1)[1]
    merge = re.search(r"MERGE INTO FDP_MDM\.CURATED\.DIM_BANK_ACCOUNT.*?;", proc, re.S).group(0)
    return merge.replace(":RUN_ID", f"'{run_id}'").rstrip(";")


def test_treasury_sample_loads_landing_and_curated(spark, warehouse):
    n = ingest_treasury_bank_accounts.run(spark, str(SAMPLE), warehouse, run_id="t-3474")
    assert n == 9
    landed = warehouse.query("SELECT * FROM FDP_MDM.LANDING.BANK_ACCOUNT_RAW ORDER BY BANK_ACCOUNT_ID").set_index("BANK_ACCOUNT_ID")
    de = landed.loc["DE01:DEUTDEFF:DE89370400440532013000"]
    assert pd.isna(de["ROUTING_CODE"])
    assert landed.loc["GB01:BARCGB22:GB29NWBK60161331926819", "ROUTING_CODE"] == "200000"
    assert landed["ACCOUNT_NUMBER"].str.fullmatch(r"[A-Z0-9]+").all()

    warehouse.execute(_sp_load_bank_accounts_merge("t-3474"))
    curated = warehouse.query("SELECT COUNT(*) AS N, COUNT(DISTINCT ENTITY_CODE) AS E FROM FDP_MDM.CURATED.DIM_BANK_ACCOUNT")
    assert (curated["N"][0], curated["E"][0]) == (9, 8)
    masked = warehouse.query("SELECT ACCOUNT_NUMBER_MASKED FROM FDP_MDM.CONSUMPTION.VW_BANK_ACCOUNT WHERE ENTITY_CODE = 'JP01'")
    assert masked["ACCOUNT_NUMBER_MASKED"][0] == "****4567"


def test_treasury_rerun_is_idempotent(spark, warehouse):
    for run_id in ("t-a", "t-b"):
        ingest_treasury_bank_accounts.run(spark, str(SAMPLE), warehouse, run_id=run_id)
        warehouse.execute(_sp_load_bank_accounts_merge(run_id))
    assert warehouse.query("SELECT COUNT(*) AS N FROM FDP_MDM.CURATED.DIM_BANK_ACCOUNT")["N"][0] == 9


def test_treasury_rejects_bad_bic(spark, warehouse, tmp_path):
    p = tmp_path / "bad_bic.csv"
    p.write_text(HEADER + "US01,JPMorgan Chase,CHAS-US33,021000021,4857 2201 9934,USD,OPERATING,ACTIVE,2010-06-10\n")
    with pytest.raises(ExpectationError, match="swift_bic"):
        ingest_treasury_bank_accounts.run(spark, str(p), warehouse, run_id="t-bad")
    assert warehouse.query("SELECT COUNT(*) AS N FROM FDP_MDM.LANDING.BANK_ACCOUNT_RAW")["N"][0] == 0
