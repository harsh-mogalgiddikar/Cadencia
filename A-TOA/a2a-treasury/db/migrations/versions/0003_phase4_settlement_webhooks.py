"""Phase 4 — Settlement tx IDs, webhooks, indexes

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-01

Adds:
  - enterprises: webhook_url, webhook_secret
  - escrow_contracts: fund_tx_id, funded_at, release_tx_id, released_at,
    refund_tx_id, refunded_at, refund_reason
  - Indexes on settlements(escrow_id), audit_logs(action), audit_logs(enterprise_id, created_at)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("enterprises", sa.Column("webhook_url", sa.String(512), nullable=True))
    op.add_column("enterprises", sa.Column("webhook_secret", sa.String(128), nullable=True))

    op.add_column("escrow_contracts", sa.Column("fund_tx_id", sa.String(128), nullable=True))
    op.add_column("escrow_contracts", sa.Column("funded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("escrow_contracts", sa.Column("release_tx_id", sa.String(128), nullable=True))
    op.add_column("escrow_contracts", sa.Column("released_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("escrow_contracts", sa.Column("refund_tx_id", sa.String(128), nullable=True))
    op.add_column("escrow_contracts", sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("escrow_contracts", sa.Column("refund_reason", sa.Text(), nullable=True))

    op.create_index("ix_settlements_escrow_id", "settlements", ["escrow_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_timestamp", "audit_logs", ["entity_id", "timestamp"])


def downgrade() -> None:
    op.drop_index("ix_audit_logs_entity_timestamp", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_settlements_escrow_id", table_name="settlements")

    op.drop_column("escrow_contracts", "refund_reason")
    op.drop_column("escrow_contracts", "refunded_at")
    op.drop_column("escrow_contracts", "refund_tx_id")
    op.drop_column("escrow_contracts", "released_at")
    op.drop_column("escrow_contracts", "release_tx_id")
    op.drop_column("escrow_contracts", "funded_at")
    op.drop_column("escrow_contracts", "fund_tx_id")

    op.drop_column("enterprises", "webhook_secret")
    op.drop_column("enterprises", "webhook_url")
