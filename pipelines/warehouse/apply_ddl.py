"""Apply snowflake/sql/*.sql to the configured warehouse and report what applied.

python -m pipelines.warehouse.apply_ddl --engine duckdb [--path pipelines/.local/fdp_mdm.duckdb]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .base import get_warehouse

SQL_DIR = Path(__file__).resolve().parents[2] / "snowflake" / "sql"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default="duckdb")
    ap.add_argument("--path", default=":memory:")
    args = ap.parse_args()
    import os

    os.environ["MDM_WAREHOUSE"] = args.engine
    wh = get_warehouse(path=args.path) if args.engine == "duckdb" else get_warehouse()
    result = (
        wh.apply_ddl_dir(SQL_DIR)
        if hasattr(wh, "apply_ddl_dir")
        else wh.apply_ddl("\n".join(p.read_text() for p in sorted(SQL_DIR.glob("*.sql"))))
    )
    print(f"applied {len(result.applied)} statements, skipped {len(result.skipped)}")
    for head, reason in result.skipped:
        print(f"  skipped: {head!r:60} {reason}")


if __name__ == "__main__":
    main()
