"""vendors, steward change requests

Revision ID: 0003
Revises: 0002
Create Date: 2022-01-11
"""

import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "vendors",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("vendor_id", sa.String(10), nullable=False, unique=True, index=True),
        sa.Column("legal_name", sa.String(200), nullable=False),
        sa.Column("tax_id", sa.String(32), nullable=True, index=True),
        sa.Column("tax_id_normalized", sa.String(32), nullable=True, index=True),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("payment_terms", sa.String(8), nullable=False, server_default="NET30"),
        sa.Column("default_cost_center_code", sa.String(6), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("golden_record_id", sa.String(36), nullable=True, index=True),
        sa.Column("source_system", sa.String(20), nullable=False, server_default="SAP"),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "change_requests",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("entity_type", sa.String(20), nullable=False, index=True),
        sa.Column("entity_key", sa.String(32), nullable=False, index=True),
        sa.Column("action", sa.String(10), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
        sa.Column("requested_by", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="PENDING", index=True),
        sa.Column("reviewed_by", sa.String(64), nullable=True),
        sa.Column("review_note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("reviewed_at", sa.DateTime, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("change_requests")
    op.drop_table("vendors")
