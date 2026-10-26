"""TD-01 parity: every runtime normalises tax ids exactly like api/app/validators.py:normalize_tax_id.

The Snowflake UDF is checked on DuckDB in test_warehouse_adapter.py::test_udf_matches_api_normalizer.
"""

import json
import shutil
import subprocess

import pytest

from api.app.validators import normalize_tax_id
from pipelines.jobs.match_merge_vendors import build_match_groups
from pipelines.tests.conftest import ROOT

VECTORS = json.loads((ROOT / "data/golden/normalize_tax_id.json").read_text())["vectors"]


@pytest.mark.parametrize("v", VECTORS, ids=lambda v: repr(v["raw"]))
def test_api_matches_golden_vectors(v):
    assert normalize_tax_id(v["raw"]) == v["expected"]


def test_pyspark_matches_golden_vectors(spark):
    rows = [(f"V{i:07d}", "Acme", v["raw"], "DE", "200026", "SAP") for i, v in enumerate(VECTORS)]
    df = spark.createDataFrame(
        rows,
        "vendor_id string, legal_name string, tax_id string, country_code string,"
        " default_cost_center_code string, source_system string",
    )
    got = {r["vendor_id"]: r["tax_id_normalized"] for r in build_match_groups(df, "parity").collect()}
    assert [got[f"V{i:07d}"] for i in range(len(VECTORS))] == [v["expected"] for v in VECTORS]


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_ui_matches_golden_vectors():
    script = (
        "import { normalizeTaxId } from './web/src/lib/format.ts';"
        "console.log(JSON.stringify(JSON.parse(process.argv[1]).map(normalizeTaxId)))"
    )
    out = subprocess.run(
        ["node", "--input-type=module", "-e", script, json.dumps([v["raw"] for v in VECTORS])],
        cwd=ROOT, capture_output=True, text=True, check=True,
    ).stdout
    assert json.loads(out) == [v["expected"] for v in VECTORS]
