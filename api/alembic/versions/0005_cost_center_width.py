"""widen cost center codes 6 -> 10 for S/4 (MBA-3472)

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-26
"""

import sqlalchemy as sa
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_COLUMNS = [
    ("cost_centers", "cost_center_code", False),
    ("cost_centers", "parent_cost_center_code", True),
    ("vendors", "default_cost_center_code", True),
]


def _alter(old: int, new: int) -> None:
    for table, column, nullable in _COLUMNS:
        with op.batch_alter_table(table) as batch:
            batch.alter_column(column, existing_type=sa.String(old), type_=sa.String(new), existing_nullable=nullable)


def upgrade() -> None:
    _alter(6, 10)


def downgrade() -> None:
    bind = op.get_bind()
    for table, column, _ in _COLUMNS:
        wide = bind.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE length({column}) > 6")).scalar()
        if wide:
            raise RuntimeError(f"cannot downgrade: {wide} rows in {table}.{column} are wider than 6 characters")
    _alter(10, 6)
