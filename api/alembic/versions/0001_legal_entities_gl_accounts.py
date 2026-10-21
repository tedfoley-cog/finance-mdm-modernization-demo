"""legal entities and GL accounts

Revision ID: 0001
Revises:
Create Date: 2021-03-18
"""

import sqlalchemy as sa
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "legal_entities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("entity_code", sa.String(4), nullable=False, unique=True, index=True),
        sa.Column("legal_name", sa.String(200), nullable=False),
        sa.Column("country_code", sa.String(2), nullable=False),
        sa.Column("functional_currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
    )
    op.create_table(
        "gl_accounts",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_number", sa.String(8), nullable=False, unique=True, index=True),
        sa.Column("description", sa.String(120), nullable=False),
        sa.Column("account_type", sa.String(16), nullable=False),
        sa.Column("normal_balance", sa.String(2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
    )


def downgrade() -> None:
    op.drop_table("gl_accounts")
    op.drop_table("legal_entities")
