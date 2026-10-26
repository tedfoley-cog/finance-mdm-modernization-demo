import pytest

from pipelines.framework.expectations import ExpectationError
from pipelines.jobs import ingest_ebs_cost_centers, ingest_sap_vendors, match_merge_vendors
from pipelines.tests.conftest import ROOT

SAMPLES = ROOT / "data" / "samples"


def test_ebs_cost_centers_land_padded(spark, warehouse):
    n = ingest_ebs_cost_centers.run(spark, str(SAMPLES / "ebs_cost_centers_extract.csv"), warehouse, run_id="t1")
    assert n > 100
    df = warehouse.query("SELECT COST_CENTER_CODE FROM FDP_MDM.LANDING.COST_CENTER_RAW")
    assert df["COST_CENTER_CODE"].str.len().eq(10).all()


def test_ebs_rejects_bad_code(spark, warehouse, tmp_path):
    p = tmp_path / "bad.csv"
    p.write_text(
        "LEDGER_ENTITY,SEGMENT2,SEGMENT2_DESC,PARENT_SEGMENT2,MANAGER_ID,PROFIT_CENTER,ENABLED_FLAG\nUS01,12A456,Broken,,E1,PC1,Y\n"
    )
    with pytest.raises(ExpectationError):
        ingest_ebs_cost_centers.run(spark, str(p), warehouse, run_id="t2")


def test_vendor_match_merge_groups_duplicates(spark, warehouse):
    ingest_sap_vendors.run(spark, str(SAMPLES / "sap_lfa1_extract.psv"), warehouse, run_id="t3")
    match_merge_vendors.run(spark, warehouse, run_id="t3")
    groups = warehouse.query(
        "SELECT GOLDEN_RECORD_ID, COUNT(*) AS N FROM FDP_MDM.CURATED.VENDOR_MATCH_GROUPS GROUP BY 1 HAVING COUNT(*) > 1"
    )
    # Four vendors are entered twice with differently formatted tax ids. Lone Star (hyphen) and Bangalore (case)
    # are grouped; Rheinland and Yorkshire (space-separated VAT ids) are NOT, because the PySpark normaliser only
    # strips hyphens while the API and the Snowflake UDF also strip whitespace. See docs/tech-debt.md (TD-01).
    assert len(groups) == 2, groups
    dim = warehouse.query("SELECT COUNT(*) AS N FROM FDP_MDM.CURATED.DIM_VENDOR")["N"][0]
    assert dim == 34
