from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_session
from ..services import change_requests

router = APIRouter(prefix="/api/cost-centers", tags=["cost-centers"])


@router.get("", response_model=list[schemas.CostCenterOut])
def list_cost_centers(
    session: Session = Depends(get_session),
    entity_code: str | None = Query(default=None, max_length=4),
    q: str | None = Query(default=None, description="prefix match on cost_center_code or description"),
    status: str = Query(default="ACTIVE"),
    limit: int = Query(default=200, le=1000),
):
    stmt = select(models.CostCenter).where(models.CostCenter.status == status)
    if entity_code:
        stmt = stmt.where(models.CostCenter.entity_code == entity_code)
    if q:
        stmt = stmt.where(models.CostCenter.cost_center_code.like(f"{q}%") | models.CostCenter.description.ilike(f"%{q}%"))
    return session.scalars(stmt.order_by(models.CostCenter.cost_center_code).limit(limit)).all()


@router.get("/{entity_code}/{cost_center_code}", response_model=schemas.CostCenterOut)
def get_cost_center(entity_code: str, cost_center_code: str, session: Session = Depends(get_session)):
    row = session.scalar(
        select(models.CostCenter).where(
            models.CostCenter.entity_code == entity_code,
            models.CostCenter.cost_center_code == cost_center_code,
        )
    )
    if row is None:
        raise HTTPException(404, "cost center not found")
    return row


@router.get("/{entity_code}/{cost_center_code}/children", response_model=list[schemas.CostCenterOut])
def list_children(entity_code: str, cost_center_code: str, session: Session = Depends(get_session)):
    stmt = select(models.CostCenter).where(
        models.CostCenter.entity_code == entity_code,
        models.CostCenter.parent_cost_center_code == cost_center_code,
    )
    return session.scalars(stmt.order_by(models.CostCenter.cost_center_code)).all()


@router.post("", response_model=schemas.ChangeRequestOut, status_code=202)
def request_cost_center(body: schemas.CostCenterCreate, session: Session = Depends(get_session)):
    payload = body.model_dump(exclude={"requested_by"})
    key = f"{body.entity_code}:{body.cost_center_code}"
    return change_requests.queue_change(session, "cost_center", key, "CREATE", payload, body.requested_by)


@router.put("/{entity_code}/{cost_center_code}", response_model=schemas.ChangeRequestOut, status_code=202)
def request_cost_center_update(
    entity_code: str,
    cost_center_code: str,
    body: schemas.CostCenterCreate,
    session: Session = Depends(get_session),
):
    if (entity_code, cost_center_code) != (body.entity_code, body.cost_center_code):
        raise HTTPException(422, "path and body keys differ")
    payload = body.model_dump(exclude={"requested_by"})
    key = f"{entity_code}:{cost_center_code}"
    return change_requests.queue_change(session, "cost_center", key, "UPDATE", payload, body.requested_by)
