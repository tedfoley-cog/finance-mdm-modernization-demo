from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models, schemas
from ..db import get_session

router = APIRouter(prefix="/api/gl-accounts", tags=["gl-accounts"])


@router.get("", response_model=list[schemas.GLAccountOut])
def list_gl_accounts(session: Session = Depends(get_session)):
    return session.scalars(select(models.GLAccount).order_by(models.GLAccount.account_number)).all()


@router.get("/{account_number}", response_model=schemas.GLAccountOut)
def get_gl_account(account_number: str, session: Session = Depends(get_session)):
    row = session.scalar(select(models.GLAccount).where(models.GLAccount.account_number == account_number))
    if row is None:
        raise HTTPException(404, "gl account not found")
    return row
