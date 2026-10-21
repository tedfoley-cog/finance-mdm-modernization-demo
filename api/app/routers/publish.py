from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_session
from ..services import publish as svc

router = APIRouter(prefix="/api/publish", tags=["publish"])


@router.get("/runs", response_model=list[schemas.PublishRunOut])
def list_runs(session: Session = Depends(get_session)):
    return session.scalars(select(models.PublishRun).order_by(models.PublishRun.created_at.desc()).limit(50)).all()


@router.post("", response_model=schemas.PublishRunOut, status_code=201)
def publish(body: schemas.PublishRequest, session: Session = Depends(get_session)):
    return svc.publish(session, body.entity_type, body.requested_by)


@router.get("/summary", response_model=schemas.ImpactSummary)
def summary(session: Session = Depends(get_session)):
    def count(model, *where):
        return session.scalar(select(func.count()).select_from(model).where(*where)) or 0

    last = session.scalar(select(models.PublishRun).order_by(models.PublishRun.created_at.desc()).limit(1))
    return schemas.ImpactSummary(
        pending_change_requests=count(models.ChangeRequest, models.ChangeRequest.status == "PENDING"),
        vendors=count(models.Vendor, models.Vendor.status == "ACTIVE"),
        cost_centers=count(models.CostCenter, models.CostCenter.status == "ACTIVE"),
        gl_accounts=count(models.GLAccount),
        last_publish=last,
    )
