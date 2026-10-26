# Technical-debt register

Maintained by the stewards of the LedgerCore MDM platform. Each item has an owner decision attached; items are
closed by a PR that links back here. `python -m tools.depgraph dupes` is the source for TD-01/TD-02; the rest were
found during incident reviews.

| ID | Area | Debt | Risk | Status |
|----|------|------|------|--------|
| TD-01 | Tax-id normalisation | Six copies of "normalise a tax id" across React (`web/src/lib/format.ts`), FastAPI (`api/app/validators.py`), PySpark (`pipelines/jobs/match_merge_vendors.py`), Snowflake (`FDP_MDM.UTIL.FN_NORMALIZE_TAX_ID`) and legacy (`legacy/mdm_batch_v1/vendor_dedupe.py`, `sql/vendor_dedupe_v1.sql`). Three behaviours: API/UI/UDF strip whitespace, hyphen, dot; PySpark strips hyphen only; legacy strips every non-alphanumeric. | Match/merge misses duplicates whose VAT id is space-separated (DE, GB vendors); the API duplicate finder and the nightly Snowflake merge disagree about which vendors are the same. Observed in the Oct-2025 vendor-master reconciliation. | Open |
| TD-02 | Cost center code width | Width `6` is hard-coded in 17 places across every layer (SQLAlchemy `String(6)`, Pydantic `max_length=6`, Snowflake `VARCHAR(6)`, UI constant and regex, PySpark `lpad`, Terraform `cost_center_code_width`, legacy fixed-width offsets). | Any ERP-driven widening (S/4 uses 10) has to be found by hand. Terraform exposes a variable that the API and UI do not read. | Resolved – MBA-3472 widened every copy to 10 (API accepts 6–10 digits; Alembic `0005`). The width is still duplicated per layer; `depgraph dupes` keeps them consistent |
| TD-03 | Legacy fixed-width loader | `legacy/mdm_batch_v1/cc_loader.py` still runs nightly for APAC entities (`aws_glue_job.legacy_cc_loader`) and writes straight into `CURATED.DIM_COST_CENTER`, bypassing landing, expectations and the publish log. | Two writers to one curated table; no lineage for APAC rows; fixed byte offsets break on any width change. | Open – retirement needs the EBS APAC extract migrated to `ebs_cost_centers` contract |
| TD-04 | Slash handling in tax ids | `normalize_tax_id` keeps `/` so Brazilian CNPJ `12.345.678/0001-90` normalises to `12345678/000190`. Legacy strips it. No decision recorded on the canonical form. | Duplicate CNPJ vendors with and without the slash are not matched. | Decision needed |
| TD-05 | Change-request payload stored as JSON text | `change_requests.payload` is a `Text` column holding JSON; RDS is PostgreSQL and could use `JSONB`. | No indexing/querying of pending payloads; the review UI re-parses on the client. | Open – low |
| TD-06 | Environment branches carry code | `env/prod` has a hotfix to `ingest_sap_vendors` (`LOEVM` deletion flag, INC-48112) that was never backported to `main`; `env/qa` widened `profit_center_code` ahead of `main` (MDM-2291). Tracked as MBA-3475. | Next promotion from `main` would silently revert the production fix. | Open – see `python -m tools.depgraph drift env/qa env/prod` |

## Resolved
_None yet._
