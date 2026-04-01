"""add deploy_txid to escrow_contracts

Revision ID: 0008
Revises: 0007
Create Date: 2026-04-01
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "escrow_contracts",
        sa.Column("deploy_txid", sa.String(128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("escrow_contracts", "deploy_txid")
