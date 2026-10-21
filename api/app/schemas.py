from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from . import validators


class LegalEntityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    entity_code: str
    legal_name: str
    country_code: str
    functional_currency: str
    status: str


class CostCenterBase(BaseModel):
    entity_code: str = Field(min_length=4, max_length=4)
    cost_center_code: str = Field(min_length=6, max_length=6, description="6-digit ERP cost center code")
    description: str = Field(max_length=120)
    parent_cost_center_code: str | None = Field(default=None, min_length=6, max_length=6)
    manager_employee_id: str | None = Field(default=None, max_length=12)
    profit_center_code: str | None = Field(default=None, max_length=12)
    status: str = "ACTIVE"

    @field_validator("cost_center_code", "parent_cost_center_code")
    @classmethod
    def _cc_format(cls, v: str | None) -> str | None:
        return None if v is None else validators.validate_cost_center_code(v)

    @field_validator("entity_code")
    @classmethod
    def _entity_format(cls, v: str) -> str:
        return validators.validate_entity_code(v)


class CostCenterCreate(CostCenterBase):
    requested_by: str


class CostCenterOut(CostCenterBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source_system: str
    valid_from: datetime
    valid_to: datetime | None
    updated_at: datetime


class VendorBase(BaseModel):
    vendor_id: str = Field(max_length=10)
    legal_name: str = Field(max_length=200)
    tax_id: str | None = Field(default=None, max_length=32)
    country_code: str = Field(min_length=2, max_length=2)
    payment_terms: str = Field(default="NET30", max_length=8)
    default_cost_center_code: str | None = Field(default=None, min_length=6, max_length=6)
    status: str = "ACTIVE"

    @field_validator("vendor_id")
    @classmethod
    def _vendor_format(cls, v: str) -> str:
        return validators.validate_vendor_id(v)

    @field_validator("default_cost_center_code")
    @classmethod
    def _cc_format(cls, v: str | None) -> str | None:
        return None if v is None else validators.validate_cost_center_code(v)


class VendorCreate(VendorBase):
    requested_by: str


class VendorOut(VendorBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    tax_id_normalized: str | None
    golden_record_id: str | None
    source_system: str
    updated_at: datetime


class GLAccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    account_number: str
    description: str
    account_type: str
    normal_balance: str
    status: str


class ChangeRequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    entity_type: str
    entity_key: str
    action: str
    payload: str
    requested_by: str
    status: str
    reviewed_by: str | None
    review_note: str | None
    created_at: datetime
    reviewed_at: datetime | None


class ReviewDecision(BaseModel):
    reviewer: str
    decision: str = Field(pattern="^(APPROVE|REJECT)$")
    note: str | None = None


class PublishRequest(BaseModel):
    entity_type: str = Field(pattern="^(vendor|cost_center|gl_account)$")
    requested_by: str


class PublishRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    entity_type: str
    record_count: int
    s3_key: str
    checksum: str
    bytes_written: int
    status: str
    created_at: datetime


class ImpactSummary(BaseModel):
    pending_change_requests: int
    vendors: int
    cost_centers: int
    gl_accounts: int
    last_publish: PublishRunOut | None
