"""Field-level validation shared by the steward API routers.

`normalize_tax_id` is the system of record for tax-id normalisation (TD-01). PySpark imports it
(pipelines/jobs/match_merge_vendors.py); the Snowflake UDF (snowflake/sql/040_udfs.sql) and the UI
(web/src/lib/format.ts) are pinned to it by data/golden/normalize_tax_id.json.
"""

from __future__ import annotations

import re

COST_CENTER_CODE_RE = re.compile(r"^\d{6}$")
ENTITY_CODE_RE = re.compile(r"^[A-Z0-9]{4}$")
GL_ACCOUNT_RE = re.compile(r"^\d{4,8}$")
VENDOR_ID_RE = re.compile(r"^V\d{7,9}$")

_TAX_ID_STRIP = re.compile(r"[\s\-.]")


def normalize_tax_id(raw: str | None) -> str | None:
    """Upper-case and strip whitespace, hyphens and dots so `DE 123-456.789` -> `DE123456789`."""
    if raw is None:
        return None
    value = _TAX_ID_STRIP.sub("", raw).upper()
    return value or None


def validate_cost_center_code(code: str) -> str:
    if not COST_CENTER_CODE_RE.match(code):
        raise ValueError("cost_center_code must be exactly 6 digits")
    return code


def validate_entity_code(code: str) -> str:
    if not ENTITY_CODE_RE.match(code):
        raise ValueError("entity_code must be 4 upper-case alphanumerics")
    return code


def validate_gl_account(number: str) -> str:
    if not GL_ACCOUNT_RE.match(number):
        raise ValueError("account_number must be 4-8 digits")
    return number


def validate_vendor_id(vendor_id: str) -> str:
    if not VENDOR_ID_RE.match(vendor_id):
        raise ValueError("vendor_id must look like V0001234")
    return vendor_id
