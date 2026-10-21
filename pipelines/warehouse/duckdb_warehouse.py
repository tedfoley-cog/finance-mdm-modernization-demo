"""Local stand-in for Snowflake. Snowflake SQL is transpiled with sqlglot and executed on DuckDB so the
pipeline jobs and the DDL under snowflake/sql run end to end without a Snowflake account.

What is emulated:
  - DATABASE.SCHEMA.TABLE three-part names (DuckDB: database -> attached catalog name, here a schema prefix)
  - VARCHAR(n) widths are enforced by a CHECK constraint added at CREATE TABLE time
  - SQL UDFs (CREATE FUNCTION ... RETURNS ... AS $$ expr $$) become DuckDB macros
  - MERGE INTO is native in DuckDB >= 1.4
What is skipped (recorded in ApplyResult.skipped): STAGE, STORAGE INTEGRATION, TASK, PROCEDURE, COPY INTO.
"""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd
import sqlglot
from sqlglot import exp

from .base import ApplyResult, Warehouse

_SKIP_RE = re.compile(
    r"^\s*(CREATE\s+(OR\s+REPLACE\s+)?(STAGE|TASK|PROCEDURE|STORAGE\s+INTEGRATION)|COPY\s+INTO|ALTER\s+TASK)", re.IGNORECASE | re.DOTALL
)
_UDF_RE = re.compile(
    r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+(?P<name>[\w.]+)\s*\((?P<args>[^)]*)\)\s*RETURNS\s+\w+(\([^)]*\))?\s*"
    r"LANGUAGE\s+SQL\s*AS\s*\$\$(?P<body>.*?)\$\$",
    re.IGNORECASE | re.DOTALL,
)
_DB_PREFIX_RE = re.compile(r"\bFDP_MDM\.", re.IGNORECASE)


def split_statements(sql_text: str) -> list[str]:
    """Split on ';' outside of $$ ... $$ blocks and strip comment-only chunks."""
    sql_text = "\n".join(re.sub(r"--.*$", "", line) for line in sql_text.splitlines())
    out, buf, in_dollar = [], [], False
    i = 0
    while i < len(sql_text):
        if sql_text.startswith("$$", i):
            in_dollar = not in_dollar
            buf.append("$$")
            i += 2
            continue
        ch = sql_text[i]
        if ch == ";" and not in_dollar:
            stmt = "".join(buf).strip()
            if stmt:
                out.append(stmt)
            buf = []
        else:
            buf.append(ch)
        i += 1
    tail = "".join(buf).strip()
    if tail:
        out.append(tail)
    cleaned = []
    for s in out:
        body = "\n".join(line for line in s.splitlines() if not line.strip().startswith("--")).strip()
        if body:
            cleaned.append(body)
    return cleaned


class DuckDBWarehouse(Warehouse):
    dialect = "snowflake"

    def __init__(self, path: str | Path = ":memory:") -> None:
        self.conn = duckdb.connect(str(path))
        for schema in ("LANDING", "CURATED", "CONSUMPTION", "UTIL"):
            self.conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")

    # -- translation -------------------------------------------------------------------------------
    def _strip_db(self, sql: str) -> str:
        return _DB_PREFIX_RE.sub("", sql)

    def transpile(self, sql: str) -> str:
        sql = self._strip_db(sql)
        sql = re.sub(r"\bAUTOINCREMENT\b", "", sql, flags=re.IGNORECASE)
        sql = re.sub(r"\bTIMESTAMP_NTZ\b", "TIMESTAMP", sql, flags=re.IGNORECASE)
        try:
            tree = sqlglot.parse_one(sql, read="snowflake")
        except sqlglot.errors.ParseError:
            return sql
        if isinstance(tree, exp.Create) and tree.args.get("kind") == "TABLE":
            self._add_width_checks(tree)
        return tree.sql(dialect="duckdb")

    @staticmethod
    def _add_width_checks(tree: exp.Create) -> None:
        schema = tree.this
        if not isinstance(schema, exp.Schema):
            return
        checks = []
        for col in schema.expressions:
            if isinstance(col, exp.ColumnDef) and col.kind and col.kind.this == exp.DataType.Type.VARCHAR:
                params = col.kind.expressions
                if params:
                    width = int(params[0].this.this)
                    checks.append(exp.Check(this=exp.LTE(this=exp.Length(this=exp.column(col.name)), expression=exp.Literal.number(width))))
        for c in checks:
            schema.append("expressions", c)

    def _define_macro(self, m: re.Match) -> None:
        name = self._strip_db(m["name"])
        args = ", ".join(a.strip().split()[0] for a in m["args"].split(",") if a.strip())
        # Snowflake string literals are backslash-escaped; DuckDB's are not.
        body = self._strip_db(m["body"].strip()).replace("\\\\", "\\")
        # Snowflake REGEXP_REPLACE replaces every match; DuckDB needs the explicit 'g' flag.
        body = re.sub(
            r"REGEXP_REPLACE\(([^,]+),\s*('(?:[^']|'')*'),\s*('(?:[^']|'')*')\)",
            r"REGEXP_REPLACE(\1, \2, \3, 'g')",
            body,
            flags=re.IGNORECASE,
        )
        self.conn.execute(f"CREATE OR REPLACE MACRO {name}({args}) AS {body}")

    # -- Warehouse API -----------------------------------------------------------------------------
    def execute(self, sql: str) -> None:
        self.conn.execute(self.transpile(sql))

    def query(self, sql: str) -> pd.DataFrame:
        return self.conn.execute(self.transpile(sql)).df()

    def load_dataframe(self, df: pd.DataFrame, table: str, mode: str = "append") -> int:
        table = self._strip_db(table)
        self.conn.register("_incoming", df)
        if mode == "overwrite":
            self.conn.execute(f"DELETE FROM {table}")
        cols = ", ".join(df.columns)
        self.conn.execute(f"INSERT INTO {table} ({cols}) SELECT {cols} FROM _incoming")
        self.conn.unregister("_incoming")
        return len(df)

    def apply_ddl(self, sql_text: str) -> ApplyResult:
        result = ApplyResult()
        for stmt in split_statements(sql_text):
            head = " ".join(stmt.split()[:4])
            if _SKIP_RE.match(stmt):
                result.skipped.append((head, "not representable in DuckDB"))
                continue
            if re.match(r"^\s*CREATE\s+(DATABASE|SCHEMA)", stmt, re.IGNORECASE):
                result.skipped.append((head, "schemas pre-created"))
                continue
            udf = _UDF_RE.match(stmt)
            if udf:
                self._define_macro(udf)
                result.applied.append(head)
                continue
            self.execute(stmt)
            result.applied.append(head)
        return result

    def apply_ddl_dir(self, directory: str | Path) -> ApplyResult:
        total = ApplyResult()
        for path in sorted(Path(directory).glob("*.sql")):
            r = self.apply_ddl(path.read_text())
            total.applied += r.applied
            total.skipped += r.skipped
        return total
