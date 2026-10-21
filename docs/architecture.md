# LedgerCore MDM — architecture

```
 React/Vite steward console ──► FastAPI steward API ──► RDS PostgreSQL (SQLAlchemy + Alembic)
        web/                        api/                  api/alembic
                                      │ POST /api/publish
                                      ▼
                             S3 publish bucket (JSONL golden records)
                                      │ S3 event
                                      ▼
                     Lambda publish_notifier ──► Snowflake SQL API: CALL FDP_MDM.UTIL.SP_LOAD_*
                                                             │
 Source extracts (SAP LFA1, Oracle EBS) ──► Glue/PySpark jobs ─┴─► FDP_MDM.LANDING ──► CURATED ──► CONSUMPTION
        data/samples/                        pipelines/jobs/            snowflake/sql/
                                      ▲
                          Step Functions nightly_mdm orchestrates ingest → match/merge → legacy cc_loader (APAC)
                          infra/terraform/
```

## Layers and where they live

| Layer | Path | Notes |
|-------|------|-------|
| Steward UI | `web/` | React 19 + Vite + TypeScript. Cost centers, vendors (with duplicate candidates), review queue (four-eyes), publish runs. |
| Steward API | `api/app` | FastAPI, SQLAlchemy 2.x, Pydantic v2. Every create/update is a `ChangeRequest`; approval applies it. |
| Operational DB | `api/alembic` | PostgreSQL on RDS; SQLite locally. Four migrations 2021→2024. |
| Pipelines | `pipelines/` | PySpark 3.5+ jobs with a source-contract registry (`pipelines/sources/*.yaml`) and expectations. |
| Warehouse adapter | `pipelines/warehouse` | `Warehouse` interface; `SnowflakeWarehouse` for AWS, `DuckDBWarehouse` locally/CI (Snowflake SQL transpiled with sqlglot). |
| Warehouse model | `snowflake/sql` | `FDP_MDM` database: LANDING, CURATED, CONSUMPTION, UTIL (procedures, task, UDFs). |
| Infrastructure | `infra/terraform` | RDS, S3, Glue, Lambda, Step Functions, ECS/Fargate API, IAM, SSM, Secrets Manager. `envs/*.tfvars` per environment. |
| Legacy | `legacy/mdm_batch_v1` | 2019 fixed-width loader + v1 dedupe SQL, still deployed as a Glue job for APAC. |
| Dependency graph | `tools/depgraph` | Deterministic cross-stack graph (`depgraph/graph.json`), impact / dupes / drift queries, HTML report. |
| Agent skills | `.agents/skills` | `impact-analysis`, `tech-debt-reduction`, `pipeline-onboarding`, `mdm-change-delivery`. |

## Environments and branches

`main` → `env/qa` → `env/prod`. Environment branches should differ from `main` only in `infra/terraform/envs/*.tfvars`.
CI's `depgraph` job runs `drift` nightly and fails when code lives only on an env branch.

## Local run

```bash
python -m venv .venv && . .venv/bin/activate && pip install -e ".[dev]"
python api/seed.py                                   # SQLite + sample data
uvicorn api.app.main:app --reload --port 8000
cd web && npm ci && npm run dev                      # http://localhost:5173, proxies /api
pytest                                               # API + DuckDB pipelines + depgraph
python -m tools.depgraph impact cost_center_code --attr width --html /tmp/impact.html
```
