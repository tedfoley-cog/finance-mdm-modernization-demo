---
name: impact-analysis
description: Cross-stack impact analysis for a proposed change to the LedgerCore MDM platform (React UI, FastAPI, RDS/Alembic, PySpark, Snowflake, Terraform, legacy batch, env branches). Use when a ticket asks "what breaks if we change X", before a migration or release, or when triaging a defect or incident to find every affected module, API, database object, cloud resource and integration.
---

# Impact analysis

Deterministic first, judgment second. The repo ships a dependency graph tool; run it before reading code so the
report is complete and reproducible, then use the code to explain *why* each hit matters.

## Procedure

1. **Name the change precisely.** Turn the ticket into one or more graph terms: a field (`cost_center_code`),
   a route (`/api/vendors`), a Snowflake object (`FDP_MDM.CURATED.DIM_VENDOR`), a Terraform variable, a job.
   If the ticket is about a field *width or format*, add `--attr width`.
2. **Query the graph** (never hand-grep first):
   ```bash
   python -m tools.depgraph build --check          # graph must be fresh; if stale, rebuild and note it
   python -m tools.depgraph impact <term> [--attr width] --html /tmp/impact.html
   python -m tools.depgraph dupes                   # sibling copies that must change together
   python -m tools.depgraph drift env/qa env/prod   # what the environments carry that main does not
   ```
   Seeds (`*`) are direct hits; the rest are 1–2 hops away. Read every layer, including `legacy` and `config`.
3. **Confirm each hit in code.** Open the file:line for every seed and every writer/reader edge. Classify:
   - **Must change** – holds the value/width/format being changed (model column, DDL, validator, UI constant,
     source-contract expectation, tfvars, legacy parser offsets).
   - **Must re-test** – reads or transforms the field (views, match/merge, publish, Lambda, Step Function).
   - **Unaffected but adjacent** – say so explicitly; silence reads as "missed".
4. **Check environment drift.** For each `env/*` branch, list commits not on `main` and whether they touch any
   node in the impact set. A hotfix that lives only on `env/prod` is a release risk and goes in the report.
5. **Check the data.** Run the API tests and the DuckDB pipeline tests (`pytest`). For width changes, run the
   warehouse adapter test that enforces `VARCHAR(n)` so you can state whether existing data fits.
6. **Write the report** (Markdown, this order): change summary → table of affected nodes grouped by layer with
   file:line and the classification → environment drift → order of operations (DB migration before API before
   UI; landing before curated before views; Terraform variable before Glue job) → test plan → open questions.
   Attach the HTML report. If a Jira key is given, post the report as a comment on the issue.

## Rules
- Never report fewer layers than the graph does. If you believe a graph hit is a false positive, say which
  and why.
- Line references must come from the files you opened, not from memory.
- Width/format changes always include: Alembic migration, Pydantic `Field(max_length)`, SQLAlchemy `String(n)`,
  Snowflake landing + curated DDL, UI constant/regex, source YAML expectations, PySpark `lpad`, Terraform
  `cost_center_code_width` default and all three tfvars, legacy fixed-width offsets.
- Do not make the change in this skill. Hand off to `mdm-change-delivery`.
