"""Phase 3 ACF: merkle_root + anchor_tx_id on negotiations.

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "negotiations",
        sa.Column("merkle_root", sa.String(64), nullable=True),
    )
    op.add_column(
        "negotiations",
        sa.Column("anchor_tx_id", sa.String(128), nullable=True),
    )


def downgrade():
    op.drop_column("negotiations", "anchor_tx_id")
    op.drop_column("negotiations", "merkle_root")
