---
name: tech-debt-reduction
description: Find and consolidate duplicated or legacy logic in the LedgerCore MDM repo (validators copied across React, FastAPI, PySpark, Snowflake UDFs and legacy batch; parallel legacy loaders; dead Terraform). Use when a ticket mentions duplication, legacy code, inconsistent behaviour between layers, or "bring up to current standards".
---

# Technical-debt reduction

Consolidation is only safe when behaviour is pinned first. Every step below produces evidence.

## Procedure

1. **Inventory.** `python -m tools.depgraph dupes` lists each concept, its copies and whether their behaviour
   signatures diverge. Cross-check with `docs/tech-debt.md` (TD-xx register). Pick one concept per PR.
2. **Pin current behaviour with golden vectors.** Before touching code, write a table of inputs → outputs for
   every copy (e.g. `12-3456789`, `DE 123 456 789`, `12.345.678/0001-90`, `gb123456789`) and record where the
   copies disagree. Put it in the PR description. This is the decision the business has to make: which
   behaviour is correct. Default: the API (`api/app/validators.py`) is the system of record.
3. **Choose the single source of truth per runtime:**
   - Python (API, PySpark, Lambda): import from `api/app/validators.py` (PySpark via a thin UDF wrapper).
   - Snowflake: one UDF in `FDP_MDM.UTIL`, tested on DuckDB through the warehouse adapter
     (`pipelines/tests/test_warehouse_adapter.py::test_udf_matches_api_normalizer` is the pattern).
   - React: one function in `web/src/lib/format.ts`; add a Vitest/pytest parity test fed by the same vectors
     file (`data/golden/<concept>.json`).
4. **Replace, don't rewrite.** Remove each copy and point its call site at the source of truth. Legacy scripts
   that are still deployed (`infra/terraform/glue.tf` → `legacy_cc_loader`) are *retired*, not edited: add a
   feature flag or remove the Glue job, and record the retirement in `legacy/mdm_batch_v1/README.md`.
5. **Prove parity.** Run `pytest` (API + DuckDB pipelines + depgraph) and `python -m tools.depgraph build`.
   The `dupes` output for the concept must show one variant. Rebuild the graph and commit `depgraph/graph.json`.
6. **Update the register.** Mark the TD item resolved in `docs/tech-debt.md` with the PR link; add any new
   debt you found but did not fix.

## Rules
- One concept per PR; never mix a consolidation with a behaviour change unless the golden-vector table shows
  the old behaviour was a bug — then say so in the PR title.
- Do not delete legacy code that Terraform still deploys without removing/flagging the deployment in the same PR.
- Keep `depgraph build --check` green.
