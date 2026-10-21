from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_session
from ..services import change_requests as svc

router = APIRouter(prefix="/api/change-requests", tags=["change-requests"])


@router.get("", response_model=list[schemas.ChangeRequestOut])
def list_change_requests(session: Session = Depends(get_session), status: str = Query(default="PENDING")):
    stmt = select(models.ChangeRequest).where(models.ChangeRequest.status == status)
    return session.scalars(stmt.order_by(models.ChangeRequest.created_at.desc())).all()


@router.get("/{cr_id}", response_model=schemas.ChangeRequestOut)
def get_change_request(cr_id: int, session: Session = Depends(get_session)):
    cr = session.get(models.ChangeRequest, cr_id)
    if cr is None:
        raise HTTPException(404, "change request not found")
    return cr


@router.post("/{cr_id}/review", response_model=schemas.ChangeRequestOut)
def review_change_request(cr_id: int, body: schemas.ReviewDecision, session: Session = Depends(get_session)):
    cr = session.get(models.ChangeRequest, cr_id)
    if cr is None:
        raise HTTPException(404, "change request not found")
    try:
        svc.review(session, cr, body.reviewer, body.decision, body.note)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    session.refresh(cr)
    return cr
