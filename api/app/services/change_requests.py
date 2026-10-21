"""Steward workflow: every create/update is queued as a ChangeRequest and applied on approval."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, validators


def queue_change(
    session: Session, entity_type: str, entity_key: str, action: str, payload: dict, requested_by: str
) -> models.ChangeRequest:
    cr = models.ChangeRequest(
        entity_type=entity_type,
        entity_key=entity_key,
        action=action,
        payload=json.dumps(payload, default=str),
        requested_by=requested_by,
    )
    session.add(cr)
    session.commit()
    session.refresh(cr)
    return cr


def apply_change(session: Session, cr: models.ChangeRequest) -> None:
    payload = json.loads(cr.payload)
    if cr.entity_type == "cost_center":
        _apply_cost_center(session, cr, payload)
    elif cr.entity_type == "vendor":
        _apply_vendor(session, cr, payload)
    else:
        raise ValueError(f"unsupported entity_type {cr.entity_type}")


def _apply_cost_center(session: Session, cr: models.ChangeRequest, payload: dict) -> None:
    existing = session.scalar(
        select(models.CostCenter).where(
            models.CostCenter.entity_code == payload["entity_code"],
            models.CostCenter.cost_center_code == payload["cost_center_code"],
        )
    )
    if cr.action == "CREATE" and existing is None:
        session.add(models.CostCenter(**payload, source_system="MDM"))
    elif existing is not None:
        for key, value in payload.items():
            setattr(existing, key, value)
        if cr.action == "RETIRE":
            existing.status = "RETIRED"
            existing.valid_to = datetime.now(UTC)
    else:
        raise ValueError("cost center not found for update")


def _apply_vendor(session: Session, cr: models.ChangeRequest, payload: dict) -> None:
    payload["tax_id_normalized"] = validators.normalize_tax_id(payload.get("tax_id"))
    existing = session.scalar(select(models.Vendor).where(models.Vendor.vendor_id == payload["vendor_id"]))
    if cr.action == "CREATE" and existing is None:
        session.add(models.Vendor(**payload, source_system="MDM"))
    elif existing is not None:
        for key, value in payload.items():
            setattr(existing, key, value)
        if cr.action == "RETIRE":
            existing.status = "RETIRED"
    else:
        raise ValueError("vendor not found for update")


def review(session: Session, cr: models.ChangeRequest, reviewer: str, decision: str, note: str | None) -> None:
    if cr.status != "PENDING":
        raise ValueError("change request already reviewed")
    if cr.requested_by == reviewer:
        raise ValueError("four-eyes rule: requester cannot approve their own change")
    if decision == "APPROVE":
        apply_change(session, cr)
        cr.status = "APPROVED"
    else:
        cr.status = "REJECTED"
    cr.reviewed_by = reviewer
    cr.review_note = note
    cr.reviewed_at = datetime.now(UTC)
    session.commit()
