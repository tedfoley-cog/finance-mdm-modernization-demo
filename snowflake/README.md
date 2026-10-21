# Snowflake objects

DDL for the `FDP_MDM` database on the Finance Data Platform account. Files apply in numeric order.

| File | Contents |
| --- | --- |
| `000_schemas.sql` | database + LANDING / CURATED / CONSUMPTION / UTIL schemas |
| `010_tables.sql` | landing tables (publish JSONL shape) and curated dimensions |
| `020_views.sql` | consumption views used by reporting and the planning cube |
| `030_tasks.sql` | external stage, load procedures (COPY + MERGE), nightly task |
| `040_udfs.sql` | tax-id normalisation, division code, conformed key |

There is no Snowflake account in CI. `pipelines/warehouse/duckdb_warehouse.py` transpiles these files with
sqlglot and executes them on DuckDB so pipeline tests exercise the real DDL; statements DuckDB cannot
express (STAGE, TASK, STORAGE INTEGRATION, procedures) are recorded as skipped. Run
`python -m pipelines.warehouse.apply_ddl --engine duckdb` to see what applies cleanly.
