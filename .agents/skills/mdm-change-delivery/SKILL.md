---
name: mdm-change-delivery
description: Team conventions for landing any change to the LedgerCore MDM repo - branch and PR flow, required checks, Alembic/Snowflake migration ordering, environment-branch synchronisation (main -> env/qa -> env/prod) and conflict handling when several engineers touch the same modules. Use whenever implementing a ticket, backporting a hotfix, or resolving a merge conflict.
---

# MDM change delivery

## Branch and environment model
- `main` is the integration branch. `env/qa` and `env/prod` are deployment branches that must only ever be
  *ahead* of `main` by environment configuration (`infra/terraform/envs/*.tfvars`), never by code.
- A hotfix made on `env/prod` is backported to `main` in the same working session (cherry-pick, open PR,
  reference the incident). `python -m tools.depgraph drift env/qa env/prod` lists anything not yet backported;
  CI runs it nightly and fails on code drift.
- Promotion is always `main → env/qa → env/prod` by fast-forward merge after the release checklist.

## Delivering a ticket
1. Branch `devin/<ticket-key>-<slug>` from `main`. Run `impact-analysis` first if the ticket touches a shared
   field, route, table or Snowflake object; link the report in the PR.
2. Change in dependency order so every commit is deployable:
   DB (Alembic migration + model) → API schema/validators → pipelines + Snowflake DDL → Terraform variables
   and tfvars → UI → legacy (retire or adapt) → docs.
3. Migrations: Alembic revision ids are sequential (`0005_...`), `downgrade()` is real. Snowflake DDL is
   idempotent (`CREATE OR REPLACE` / `IF NOT EXISTS`) and must apply on DuckDB (`pytest pipelines/tests`).
4. Required checks before requesting review: `ruff check .`, `pytest`, `cd web && npx tsc -b && npx vite build`,
   `python -m tools.depgraph build --check`. CI runs the same four jobs.
5. PR description: ticket link, what changed per layer, impact report link, test evidence, rollout order and
   rollback. Rebuild and commit `depgraph/graph.json` whenever code structure changes.

## Conflicts between engineers
- Rebase onto `main` daily; prefer small PRs per layer when two tickets touch the same module.
- Conflicts in generated files (`depgraph/graph.json`, lockfiles): take `main`, regenerate, commit.
- Conflicts in Alembic: renumber your revision to follow the latest on `main` and update `down_revision`.
- Conflicts in Snowflake DDL or Terraform: keep both sides' statements, re-run the DuckDB DDL test, and add a
  drift note if the other change was already promoted to an env branch.
- Never resolve a conflict by deleting the other engineer's test.

## Rules
- No secrets, account identifiers or private hostnames in code, tfvars or docs.
- Do not merge; request review from the owning steward and leave the PR for a human to merge.
