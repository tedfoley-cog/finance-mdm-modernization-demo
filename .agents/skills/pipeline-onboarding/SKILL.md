---
name: pipeline-onboarding
description: Onboard a new upstream source feed into the LedgerCore MDM pipelines and Snowflake model (source contract YAML, PySpark ingest job, landing/curated DDL, Glue job + Step Functions wiring), verified locally on DuckDB without a Snowflake account. Use when asked to add a source system, a new master-data entity, or a new feed into the data lake.
---

# Pipeline onboarding

No Snowflake credentials are needed: the warehouse adapter runs the real Snowflake DDL on DuckDB via sqlglot.
A feed is "onboarded" when the sample file loads end to end in `pytest` and the graph shows the new lineage.

## Procedure

1. **Profile the sample.** Read the extract under `data/samples/` (or the path given). Record: delimiter,
   header, candidate key, nullable columns, formats that need normalising (IBAN spacing, sort codes, dates).
2. **Source contract.** Add `pipelines/sources/<name>.yaml` mirroring `sap_vendors.yaml`: `system`, `format`,
   `landing_prefix`, `target_table`, `columns` (source → target), `expectations` (`not_null`, `unique`,
   `regex`, `max_length`, `in_set`, `row_count_min`). Expectations are the acceptance criteria — write them
   from the profile, not after the job passes.
3. **Snowflake DDL.** Append a `LANDING.<ENTITY>_RAW` table and a `CURATED.DIM_<ENTITY>` table to
   `snowflake/sql/010_tables.sql` (VARCHAR widths explicit; they are enforced on DuckDB), a `CONSUMPTION` view
   if consumers need one, and a `UTIL.SP_LOAD_<ENTITY>` procedure in `030_tasks.sql` following the existing
   ones. Register the entity in the nightly task and in `infra/terraform/lambda/publish_notifier.py` if it is
   published from the API.
4. **PySpark job.** `pipelines/jobs/ingest_<name>.py` modelled on `ingest_sap_vendors.py`: `transform(raw,
   run_id)` is pure and unit-testable; `run()` reads with the contract options, enforces expectations, loads via
   `warehouse.load_dataframe`. Never import a Snowflake driver in a job.
5. **Infra.** Add an `aws_glue_job` in `infra/terraform/glue.tf` and a state in
   `infra/terraform/state_machines/nightly_mdm.asl.json`. Any new env var goes through `variables.tf` + all
   three `envs/*.tfvars`.
6. **Prove it.** Add `pipelines/tests/test_ingest_<name>.py` (loads the sample, asserts row count, a
   normalisation, and one expectation failure). Run `pytest pipelines/tests`. Then
   `python -m pipelines.warehouse.apply_ddl --engine duckdb` must apply the DDL with no new skipped statements
   other than STAGE/TASK/PROCEDURE/COPY.
7. **Graph + docs.** `python -m tools.depgraph build`; confirm `impact <name>` shows source → job → landing →
   curated → Glue. Add the feed to `docs/pipelines.md`.

## Rules
- Column widths must agree across contract `max_length`, landing DDL, curated DDL and (if applicable) the API
  model; run `depgraph dupes` to confirm one variant.
- Secrets never appear in YAML, jobs or tfvars; the Snowflake adapter reads them from the environment.
