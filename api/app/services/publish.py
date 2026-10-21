"""Publish approved golden records to the landing bucket read by the Snowflake ingest task.

Object layout (consumed by infra/terraform/lambda/publish_notifier.py and snowflake/sql/030_tasks.sql):
    s3://<publish_bucket>/<prefix>/<entity_type>/dt=<YYYY-MM-DD>/<run_id>.jsonl
Locally (MDM_PUBLISH_LOCAL_DIR set) the same layout is written to disk so pipelines/tests can read it.
"""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models
from ..config import settings

ENTITY_MODELS = {
    "vendor": models.Vendor,
    "cost_center": models.CostCenter,
    "gl_account": models.GLAccount,
}

PUBLISH_COLUMNS = {
    "vendor": [
        "vendor_id",
        "legal_name",
        "tax_id",
        "tax_id_normalized",
        "country_code",
        "payment_terms",
        "default_cost_center_code",
        "status",
        "golden_record_id",
        "source_system",
    ],
    "cost_center": [
        "entity_code",
        "cost_center_code",
        "description",
        "parent_cost_center_code",
        "manager_employee_id",
        "profit_center_code",
        "status",
        "source_system",
    ],
    "gl_account": ["account_number", "description", "account_type", "normal_balance", "status"],
}


def _serialise(row: object, columns: list[str]) -> dict:
    return {c: getattr(row, c) for c in columns}


def publish(session: Session, entity_type: str, requested_by: str) -> models.PublishRun:
    model = ENTITY_MODELS[entity_type]
    rows = session.scalars(select(model).where(model.status != "RETIRED")).all()
    lines = [json.dumps(_serialise(r, PUBLISH_COLUMNS[entity_type]), default=str) for r in rows]
    body = ("\n".join(lines) + "\n").encode()
    checksum = hashlib.sha256(body).hexdigest()
    now = datetime.now(UTC)
    run_id = now.strftime("%Y%m%dT%H%M%SZ")
    key = f"{settings.publish_prefix}/{entity_type}/dt={now:%Y-%m-%d}/{run_id}.jsonl"

    local_dir = os.environ.get("MDM_PUBLISH_LOCAL_DIR")
    if local_dir:
        target = Path(local_dir) / settings.publish_bucket / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        status = "WRITTEN_LOCAL"
    else:
        import boto3  # noqa: PLC0415 - only needed when talking to real S3

        boto3.client("s3").put_object(
            Bucket=settings.publish_bucket, Key=key, Body=body, Metadata={"requested-by": requested_by, "sha256": checksum}
        )
        status = "WRITTEN_S3"

    run = models.PublishRun(
        entity_type=entity_type, record_count=len(rows), s3_key=key, checksum=checksum, bytes_written=len(body), status=status
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run
