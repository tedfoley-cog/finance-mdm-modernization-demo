"""Create the local SQLite schema and load the sample master data under data/samples.

python -m api.seed            # default sqlite:///./ledgercore.db
"""

from __future__ import annotations

import csv
from pathlib import Path

from sqlalchemy import select

from api.app import models, validators
from api.app.db import Base, SessionLocal, engine

SAMPLES = Path(__file__).resolve().parents[1] / "data" / "samples"


def load_csv(name: str) -> list[dict]:
    with (SAMPLES / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def seed() -> dict[str, int]:
    Base.metadata.create_all(engine)
    counts: dict[str, int] = {}
    with SessionLocal() as session:
        if session.scalar(select(models.LegalEntity).limit(1)) is not None:
            return {"skipped": 1}
        for row in load_csv("legal_entities.csv"):
            session.add(models.LegalEntity(**row))
        for row in load_csv("cost_centers_mdm.csv"):
            row = {k: (v or None) for k, v in row.items()}
            session.add(models.CostCenter(**row))
        for row in load_csv("vendors_mdm.csv"):
            row = {k: (v or None) for k, v in row.items()}
            row["tax_id_normalized"] = validators.normalize_tax_id(row.get("tax_id"))
            session.add(models.Vendor(**row))
        for row in load_csv("gl_accounts.csv"):
            session.add(models.GLAccount(**row))
        session.commit()
        for model in (models.LegalEntity, models.CostCenter, models.Vendor, models.GLAccount):
            counts[model.__tablename__] = len(session.scalars(select(model)).all())
    return counts


if __name__ == "__main__":
    print(seed())
