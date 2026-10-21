"""SQLAlchemy models for the MDM operational store (AWS RDS PostgreSQL in dev/qa/prod, SQLite locally).

Column widths mirror the Alembic migrations under api/alembic/versions and the Snowflake DDL under
snowflake/sql. Keep them in sync: the publish job copies these rows verbatim into the warehouse stage.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class LegalEntity(Base):
    __tablename__ = "legal_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_code: Mapped[str] = mapped_column(String(4), unique=True, index=True)
    legal_name: Mapped[str] = mapped_column(String(200))
    country_code: Mapped[str] = mapped_column(String(2))
    functional_currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")


class CostCenter(Base):
    __tablename__ = "cost_centers"
    __table_args__ = (UniqueConstraint("entity_code", "cost_center_code", name="uq_cost_center_entity_code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_code: Mapped[str] = mapped_column(String(4), ForeignKey("legal_entities.entity_code"), index=True)
    cost_center_code: Mapped[str] = mapped_column(String(6), index=True)
    description: Mapped[str] = mapped_column(String(120))
    parent_cost_center_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    manager_employee_id: Mapped[str | None] = mapped_column(String(12), nullable=True)
    profit_center_code: Mapped[str | None] = mapped_column(String(12), nullable=True)
    valid_from: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    valid_to: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    source_system: Mapped[str] = mapped_column(String(20), default="EBS")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    entity: Mapped[LegalEntity] = relationship()


class Vendor(Base):
    __tablename__ = "vendors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vendor_id: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    legal_name: Mapped[str] = mapped_column(String(200))
    tax_id: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    tax_id_normalized: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    country_code: Mapped[str] = mapped_column(String(2))
    payment_terms: Mapped[str] = mapped_column(String(8), default="NET30")
    default_cost_center_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")
    golden_record_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    source_system: Mapped[str] = mapped_column(String(20), default="SAP")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())


class GLAccount(Base):
    __tablename__ = "gl_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_number: Mapped[str] = mapped_column(String(8), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(120))
    account_type: Mapped[str] = mapped_column(String(16))
    normal_balance: Mapped[str] = mapped_column(String(2))
    status: Mapped[str] = mapped_column(String(16), default="ACTIVE")


class ChangeRequest(Base):
    """Steward approval queue. Every mutation to a master record goes through here."""

    __tablename__ = "change_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20), index=True)  # vendor | cost_center | gl_account
    entity_key: Mapped[str] = mapped_column(String(32), index=True)
    action: Mapped[str] = mapped_column(String(10))  # CREATE | UPDATE | RETIRE
    payload: Mapped[str] = mapped_column(Text)  # JSON
    requested_by: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="PENDING", index=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class PublishRun(Base):
    __tablename__ = "publish_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20))
    record_count: Mapped[int] = mapped_column(Integer)
    s3_key: Mapped[str] = mapped_column(String(255))
    checksum: Mapped[str] = mapped_column(String(64))
    bytes_written: Mapped[int] = mapped_column(Integer, default=0)
    amount_threshold: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="QUEUED")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
