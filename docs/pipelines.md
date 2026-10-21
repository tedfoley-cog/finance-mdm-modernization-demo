# Pipelines

| Feed | Contract | Job | Lands in | Schedule |
|------|----------|-----|----------|----------|
| SAP LFA1 vendors | `pipelines/sources/sap_vendors.yaml` | `pipelines/jobs/ingest_sap_vendors.py` | `FDP_MDM.LANDING.VENDOR_RAW` | nightly (Step Functions `IngestSapVendors`) |
| Oracle EBS cost centers | `pipelines/sources/ebs_cost_centers.yaml` | `pipelines/jobs/ingest_ebs_cost_centers.py` | `FDP_MDM.LANDING.COST_CENTER_RAW` | nightly |
| Vendor match/merge | — | `pipelines/jobs/match_merge_vendors.py` | `FDP_MDM.CURATED.VENDOR_MATCH_GROUPS`, `DIM_VENDOR` | nightly, after ingest |
| APAC cost centers (legacy) | fixed-width, see `legacy/mdm_batch_v1/README.md` | `legacy/mdm_batch_v1/cc_loader.py` | `FDP_MDM.CURATED.DIM_COST_CENTER` (direct) | nightly |
| Treasury bank accounts | _not onboarded_ — sample at `data/samples/treasury_bank_accounts.csv` | — | — | — |

## Running without Snowflake

`MDM_WAREHOUSE=duckdb` (default) makes every job and the DDL run on a local DuckDB file. `sqlglot` transpiles
Snowflake SQL; `VARCHAR(n)` becomes a CHECK constraint so width violations fail locally the same way they fail in
Snowflake. Stages, tasks, procedures and `COPY INTO` are reported as skipped.

```bash
python -m pipelines.warehouse.apply_ddl --engine duckdb --path pipelines/.local/fdp_mdm.duckdb
python -m pipelines.jobs.ingest_sap_vendors --input data/samples/sap_lfa1_extract.psv
python -m pipelines.jobs.match_merge_vendors
```

Set `MDM_WAREHOUSE=snowflake` plus `SNOWFLAKE_*` environment variables (from Secrets Manager in Glue) to run
against the real account. No credentials are stored in the repository.
