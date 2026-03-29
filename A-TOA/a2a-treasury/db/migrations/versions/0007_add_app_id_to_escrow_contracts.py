"""Phase 6: Add app_id to escrow_contracts for smart contract tracking.

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "escrow_contracts",
        sa.Column("app_id", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("escrow_contracts", "app_id")
