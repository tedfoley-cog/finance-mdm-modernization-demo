"""Minimal data-quality checks evaluated on a Spark DataFrame before anything is loaded."""

from __future__ import annotations

from dataclasses import dataclass

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


@dataclass
class ExpectationResult:
    name: str
    passed: bool
    failing_rows: int
    detail: str = ""


class ExpectationError(RuntimeError):
    pass


def evaluate(df: DataFrame, expectations: list[dict]) -> list[ExpectationResult]:
    results = []
    for e in expectations:
        kind, col = e["type"], e.get("column")
        if kind == "not_null":
            bad = df.filter(F.col(col).isNull()).count()
        elif kind == "unique":
            bad = df.groupBy(col).count().filter("count > 1").count()
        elif kind == "regex":
            bad = df.filter(~F.col(col).rlike(e["pattern"])).count()
        elif kind == "max_length":
            bad = df.filter(F.length(F.col(col)) > e["value"]).count()
        elif kind == "in_set":
            bad = df.filter(~F.col(col).isin(e["values"])).count()
        elif kind == "row_count_min":
            bad = 0 if df.count() >= e["value"] else 1
        else:
            raise ValueError(f"unknown expectation type {kind}")
        results.append(
            ExpectationResult(
                name=f"{kind}:{col or ''}", passed=bad == 0, failing_rows=bad, detail=str({k: v for k, v in e.items() if k != "type"})
            )
        )
    return results


def enforce(df: DataFrame, expectations: list[dict]) -> list[ExpectationResult]:
    results = evaluate(df, expectations)
    failed = [r for r in results if not r.passed]
    if failed:
        raise ExpectationError("; ".join(f"{r.name} ({r.failing_rows} rows) {r.detail}" for r in failed))
    return results
