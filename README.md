# LedgerCore MDM

Finance master data management platform: legal entities, cost centers, vendors and GL accounts are stewarded in a
React console, approved through a four-eyes change-request workflow in a FastAPI service on RDS, published to S3 and
loaded into the `FDP_MDM` Snowflake database by PySpark/Glue jobs orchestrated with Step Functions.

The platform has grown since 2019 across several stacks and teams; see [docs/architecture.md](docs/architecture.md)
for the current shape, [docs/tech-debt.md](docs/tech-debt.md) for the debt register and
[docs/pipelines.md](docs/pipelines.md) for the feeds.

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
python api/seed.py && uvicorn api.app.main:app --reload --port 8000
cd web && npm ci && npm run dev          # steward console on http://localhost:5173
pytest                                   # API, pipelines (on DuckDB), dependency graph
```

## Dependency graph

```bash
python -m tools.depgraph impact cost_center_code --attr width   # every layer that holds the 6-char width
python -m tools.depgraph dupes                                   # duplicated logic and whether copies diverge
python -m tools.depgraph drift env/qa env/prod                   # what the environment branches carry
python -m tools.depgraph report depgraph/report.html --impact cost_center_code --attr width --drift env/qa env/prod
```

`depgraph/graph.json` is committed and checked in CI (`build --check`); rebuild it when structure changes.

## Repository layout

`api/` FastAPI + SQLAlchemy + Alembic · `web/` React/Vite · `pipelines/` PySpark jobs, source contracts, warehouse
adapter · `snowflake/sql/` DDL, views, procedures, UDFs · `infra/terraform/` AWS · `legacy/` 2019 batch still in
service · `tools/depgraph/` cross-stack graph · `.agents/skills/` agent playbooks · `data/samples/` synthetic extracts.
