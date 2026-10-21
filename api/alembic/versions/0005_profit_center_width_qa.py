"""widen profit_center_code to 12 for the EU ledger pilot (QA only, pending main)

Revision ID: 0005_profit_center_width
Revises: 0004_publish_runs_profit_center
Create Date: 2026-10-09
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_profit_center_width"
down_revision = "0004_publish_runs_profit_center"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("cost_centers") as batch:
        batch.alter_column("profit_center_code", type_=sa.String(12), existing_type=sa.String(10))


def downgrade() -> None:
    with op.batch_alter_table("cost_centers") as batch:
        batch.alter_column("profit_center_code", type_=sa.String(10), existing_type=sa.String(12))
