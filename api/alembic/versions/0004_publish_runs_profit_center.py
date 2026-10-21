"""publish runs; profit center on cost centers (S/4 readiness, phase 1)

Revision ID: 0004
Revises: 0003
Create Date: 2024-09-30
"""

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "publish_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("entity_type", sa.String(20), nullable=False),
        sa.Column("record_count", sa.Integer, nullable=False),
        sa.Column("s3_key", sa.String(255), nullable=False),
        sa.Column("checksum", sa.String(64), nullable=False),
        sa.Column("bytes_written", sa.Integer, nullable=False, server_default="0"),
        sa.Column("amount_threshold", sa.Numeric(14, 2), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="QUEUED"),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    with op.batch_alter_table("cost_centers") as batch:
        batch.add_column(sa.Column("profit_center_code", sa.String(10), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("cost_centers") as batch:
        batch.drop_column("profit_center_code")
    op.drop_table("publish_runs")
