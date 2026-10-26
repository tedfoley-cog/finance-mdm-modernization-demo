# Pipelines

| Feed | Contract | Job | Lands in | Schedule |
|------|----------|-----|----------|----------|
| SAP LFA1 vendors | `pipelines/sources/sap_vendors.yaml` | `pipelines/jobs/ingest_sap_vendors.py` | `FDP_MDM.LANDING.VENDOR_RAW` | nightly (Step Functions `IngestSapVendors`) |
| Oracle EBS cost centers | `pipelines/sources/ebs_cost_centers.yaml` | `pipelines/jobs/ingest_ebs_cost_centers.py` | `FDP_MDM.LANDING.COST_CENTER_RAW` | nightly |
| Vendor match/merge | — | `pipelines/jobs/match_merge_vendors.py` | `FDP_MDM.CURATED.VENDOR_MATCH_GROUPS`, `DIM_VENDOR` | nightly, after ingest |
| APAC cost centers (legacy) | fixed-width, see `legacy/mdm_batch_v1/README.md` | `legacy/mdm_batch_v1/cc_loader.py` | `FDP_MDM.CURATED.DIM_COST_CENTER` (direct) | nightly |
| Treasury bank accounts | `pipelines/sources/treasury_bank_accounts.yaml` | `pipelines/jobs/ingest_treasury_bank_accounts.py` | `FDP_MDM.LANDING.BANK_ACCOUNT_RAW` → `CURATED.DIM_BANK_ACCOUNT` (`UTIL.SP_LOAD_BANK_ACCOUNTS`), masked view `CONSUMPTION.VW_BANK_ACCOUNT` | nightly (Step Functions `IngestTreasuryBankAccounts`; task `TASK_NIGHTLY_BANK_ACCOUNTS`) |

## Treasury bank accounts (MBA-3474)

- Extract: comma-separated with header, one row per house-bank account (9 rows in the sample, 8 entities).
- Key: `BANK_ACCOUNT_ID = ENTITY:SWIFT_BIC:ACCOUNT_NUMBER` (unique expectation).
- Normalisation: `ACCOUNT_NUMBER` and `ROUTING_CODE` lose spaces, hyphens and dots and are upper-cased
  (`DE89 3704 0044 …` → `DE89370400440532013000`, sort code `20-00-00` → `200000`); empty routing → NULL (DE01 IBAN).
- Expectations: BIC `^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$`, ISO currency, purpose/status sets, account ≤ 34 (IBAN max).
  A bad BIC fails the job before anything lands.
- Account numbers are sensitive: consumers read `CONSUMPTION.VW_BANK_ACCOUNT` (last 4 digits + `SHA2` hashed key only).
- `SP_LOAD_BANK_ACCOUNTS(NULL)` (nightly task) merges the latest landed batch.

```bash
python -m pipelines.jobs.ingest_treasury_bank_accounts --input data/samples/treasury_bank_accounts.csv
```

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
