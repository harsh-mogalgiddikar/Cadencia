"""Phase 5: x402 delivery table + negotiation delivery columns.

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    # ── deliveries table ──────────────────────────────────────────────
    op.create_table(
        "deliveries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", UUID(as_uuid=True), nullable=False),
        sa.Column("tx_id", sa.String(128), nullable=False),
        sa.Column("amount_usdc", sa.Numeric(18, 6), nullable=False),
        sa.Column("network", sa.String(64), nullable=False,
                  server_default="algorand-testnet"),
        sa.Column("simulation", sa.Boolean, nullable=False,
                  server_default=sa.text("true")),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["session_id"], ["negotiations.session_id"],
                                ondelete="CASCADE"),
    )
    op.create_index("ix_deliveries_session_id", "deliveries", ["session_id"])

    # ── negotiation delivery columns ──────────────────────────────────
    op.add_column(
        "negotiations",
        sa.Column("delivery_status", sa.String(32), nullable=True),
    )
    op.add_column(
        "negotiations",
        sa.Column("delivery_tx_id", sa.String(128), nullable=True),
    )


def downgrade():
    op.drop_column("negotiations", "delivery_tx_id")
    op.drop_column("negotiations", "delivery_status")
    op.drop_index("ix_deliveries_session_id", table_name="deliveries")
    op.drop_table("deliveries")
