# Demo run-of-show — "one engineer, one ticket, every layer"

Audience: finance MDM / data-lake engineering leads. Length: ~25 minutes live. Persona: you are the engineer who
picked up the S/4 cost-center story this sprint.

Jira epic: [MBA-3471](https://cog-gtm.atlassian.net/browse/MBA-3471)
Repo: https://github.com/tedfoley-cog/finance-mdm-modernization-demo · DeepWiki: https://deepwiki.com/tedfoley-cog/finance-mdm-modernization-demo

| # | Show | Say | Covers their ask |
|---|------|-----|------------------|
| 1 | Jira story [MBA-3472](https://cog-gtm.atlassian.net/browse/MBA-3472) (6→10 char cost center codes) | "S/4 widens the cost-center key. Today the first week of this ticket is one engineer grepping five repos and asking around on Teams. Let's do it the other way." | Impact analysis is manual |
| 2 | DeepWiki for the repo: architecture page, then ask *"Where is the cost center code width enforced, and which Snowflake objects depend on `COST_CENTER_CODE`?"* | "Nobody on the team wrote this wiki. It is regenerated from the code, so a new joiner or an auditor gets the same answer the author would." | Long-running project through many hands; standards |
| 3 | Devin session: *"Run the impact-analysis skill for MBA-3472 and post the report to the ticket."* While it runs, open `.agents/skills/impact-analysis/SKILL.md`. | "The skill is our team's playbook: run the deterministic graph first, then confirm every hit in code, then check what lives only on env branches. Judgment on top of a tool, not instead of it." | Standard playbooks |
| 4 | Devin's comment on MBA-3472: 17 seeds across 9 layers (UI constant, Pydantic, SQLAlchemy, Alembic, PySpark `lpad`, Snowflake landing + curated DDL, Terraform var + 3 tfvars, legacy fixed-width offsets) **plus** the `env/prod` hotfix never backported. Open the HTML report. | "Every layer, with file:line. And the thing that would have bitten us at release: a production hotfix that `main` does not have." | Dependencies across code, APIs, DB objects, cloud resources; multiple code versions |
| 5 | Devin: *"Implement MBA-3472 following mdm-change-delivery."* → PR with migration `0005`, model/schema/UI/DDL/tfvars/legacy changes, tests, regenerated `depgraph/graph.json`; CI green (ruff, pytest incl. DuckDB warehouse, web build, `depgraph build --check`). | "Deployable order, not alphabetical. The DuckDB adapter ran the real Snowflake DDL so we know a 10-char key loads — without a Snowflake account in the loop." | Modernise safely; release risk |
| 6 | Second ticket [MBA-3473](https://cog-gtm.atlassian.net/browse/MBA-3473): `python -m tools.depgraph dupes` → `normalize_tax_id`: 6 copies, 3 behaviours. Devin runs `tech-debt-reduction`: golden-vector table in the PR, PySpark/UDF/UI now import or mirror the API, legacy copies retired, match/merge now groups all 4 duplicate pairs. | "That divergence is a real reconciliation incident. The PR shows the before/after per copy so the business decides the behaviour, and the register in `docs/tech-debt.md` closes TD-01." | Duplicate and legacy code, technical debt |
| 7 | Third ticket [MBA-3474](https://cog-gtm.atlassian.net/browse/MBA-3474): treasury bank-account feed. Devin runs `pipeline-onboarding`: source YAML with expectations → PySpark job → DDL → Glue + Step Functions → tests on DuckDB. Show the expectation failure on a bad BIC. | "New source to Snowflake in one PR, and we proved it loads before anyone touches a warehouse. Snowflake is swapped in by one env var." | Automate pipeline work; give engineers time back |
| 8 | [MBA-3475](https://cog-gtm.atlassian.net/browse/MBA-3475) + `drift` output + `mdm-change-delivery` conflict rules; CI drift job on `main`. | "Several developers, three branches: the playbook says where code may live and CI enforces it. Conflicts in generated files are regenerated, not hand-merged." | Team-scale use, conflicts, env sync |

## Before the call
- `python -m tools.depgraph build --check` green on `main`; `env/qa`, `env/prod` pushed with their drift commits.
- DeepWiki indexed (open the link once; first index takes a few minutes).
- Have a Devin session warm with the repo cloned; pre-run step 3 once so the ticket comment exists as a fallback.
- Backup if Devin is slow: `python -m tools.depgraph report /tmp/report.html --impact cost_center_code --attr width --drift env/qa env/prod` and open the file.

## Reset after a dry run
`git push origin :devin/mba-3472-*` for any PR branches; close the PRs; delete Devin's comments on MBA-3472..3475; keep `main` and the env branches untouched.
