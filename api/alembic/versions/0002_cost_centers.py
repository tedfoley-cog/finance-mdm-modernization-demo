"""cost centers (6-digit ERP code, scoped by legal entity)

Revision ID: 0002
Revises: 0001
Create Date: 2021-05-02
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cost_centers",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("entity_code", sa.String(4), sa.ForeignKey("legal_entities.entity_code"), nullable=False, index=True),
        sa.Column("cost_center_code", sa.String(6), nullable=False, index=True),
        sa.Column("description", sa.String(120), nullable=False),
        sa.Column("parent_cost_center_code", sa.String(6), nullable=True),
        sa.Column("manager_employee_id", sa.String(12), nullable=True),
        sa.Column("valid_from", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("valid_to", sa.DateTime, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("source_system", sa.String(20), nullable=False, server_default="EBS"),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("entity_code", "cost_center_code", name="uq_cost_center_entity_code"),
    )


def downgrade() -> None:
    op.drop_table("cost_centers")
