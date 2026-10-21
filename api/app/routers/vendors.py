from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas, validators
from ..db import get_session
from ..services import change_requests

router = APIRouter(prefix="/api/vendors", tags=["vendors"])


@router.get("", response_model=list[schemas.VendorOut])
def list_vendors(
    session: Session = Depends(get_session),
    q: str | None = Query(default=None),
    country_code: str | None = Query(default=None, max_length=2),
    status: str = Query(default="ACTIVE"),
    limit: int = Query(default=200, le=1000),
):
    stmt = select(models.Vendor).where(models.Vendor.status == status)
    if q:
        normalized = validators.normalize_tax_id(q) or q
        stmt = stmt.where(
            models.Vendor.legal_name.ilike(f"%{q}%")
            | models.Vendor.vendor_id.like(f"{q}%")
            | (models.Vendor.tax_id_normalized == normalized)
        )
    if country_code:
        stmt = stmt.where(models.Vendor.country_code == country_code)
    return session.scalars(stmt.order_by(models.Vendor.legal_name).limit(limit)).all()


@router.get("/duplicates", response_model=list[list[schemas.VendorOut]])
def potential_duplicates(session: Session = Depends(get_session)):
    """Vendors sharing a normalised tax id but holding different vendor_ids (match/merge candidates)."""
    rows = session.scalars(
        select(models.Vendor).where(models.Vendor.tax_id_normalized.is_not(None)).order_by(models.Vendor.tax_id_normalized)
    ).all()
    groups: dict[str, list[models.Vendor]] = {}
    for row in rows:
        groups.setdefault(row.tax_id_normalized, []).append(row)
    return [g for g in groups.values() if len(g) > 1]


@router.get("/{vendor_id}", response_model=schemas.VendorOut)
def get_vendor(vendor_id: str, session: Session = Depends(get_session)):
    row = session.scalar(select(models.Vendor).where(models.Vendor.vendor_id == vendor_id))
    if row is None:
        raise HTTPException(404, "vendor not found")
    return row


@router.post("", response_model=schemas.ChangeRequestOut, status_code=202)
def request_vendor(body: schemas.VendorCreate, session: Session = Depends(get_session)):
    payload = body.model_dump(exclude={"requested_by"})
    return change_requests.queue_change(session, "vendor", body.vendor_id, "CREATE", payload, body.requested_by)


@router.put("/{vendor_id}", response_model=schemas.ChangeRequestOut, status_code=202)
def request_vendor_update(vendor_id: str, body: schemas.VendorCreate, session: Session = Depends(get_session)):
    if vendor_id != body.vendor_id:
        raise HTTPException(422, "path and body vendor_id differ")
    payload = body.model_dump(exclude={"requested_by"})
    return change_requests.queue_change(session, "vendor", vendor_id, "UPDATE", payload, body.requested_by)
