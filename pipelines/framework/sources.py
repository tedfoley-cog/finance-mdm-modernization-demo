"""Source registry: one YAML per upstream system under pipelines/sources/. Jobs look their contract up here so
column mappings and quality expectations live in one place."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

SOURCES_DIR = Path(__file__).resolve().parents[1] / "sources"


@dataclass(frozen=True)
class SourceContract:
    name: str
    system: str
    format: str
    landing_prefix: str
    target_table: str
    columns: dict[str, str]  # source column -> target column
    expectations: list[dict]
    options: dict

    @property
    def target_columns(self) -> list[str]:
        return list(self.columns.values())


def load_source(name: str) -> SourceContract:
    data = yaml.safe_load((SOURCES_DIR / f"{name}.yaml").read_text())
    return SourceContract(
        name=data["name"],
        system=data["system"],
        format=data["format"],
        landing_prefix=data["landing_prefix"],
        target_table=data["target_table"],
        columns=data["columns"],
        expectations=data.get("expectations", []),
        options=data.get("options", {}),
    )


def list_sources() -> list[str]:
    return sorted(p.stem for p in SOURCES_DIR.glob("*.yaml"))
