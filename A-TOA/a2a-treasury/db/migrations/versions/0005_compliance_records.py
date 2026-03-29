"""Phase 5b — Ensure compliance_records table exists (idempotent)

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-01

Safety-net migration: creates compliance_records IF NOT EXISTS.
The table was originally created in 0002, but this ensures it
survives any partial migration or manual drop.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS compliance_records (
            record_id       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            session_id      UUID REFERENCES negotiations(session_id) ON DELETE CASCADE,
            enterprise_id   UUID REFERENCES enterprises(enterprise_id),
            purpose_code    VARCHAR(20) NOT NULL DEFAULT 'P0103',
            purpose_label   VARCHAR(255),
            transaction_type VARCHAR(20),
            inr_amount      NUMERIC(18,6),
            usdc_amount     NUMERIC(15,6),
            usd_equivalent  NUMERIC(15,6),
            limit_applicable NUMERIC(15,6),
            limit_utilization_pct NUMERIC(8,4),
            status          VARCHAR(20) NOT NULL DEFAULT 'COMPLIANT',
            warnings        JSONB,
            blocking_reasons JSONB,
            counterparty_country VARCHAR(50),
            invoice_ref     VARCHAR(100),
            checked_at      TIMESTAMPTZ DEFAULT NOW(),
            created_at      TIMESTAMPTZ DEFAULT NOW()
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_compliance_session
        ON compliance_records(session_id);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_compliance_records_enterprise_id
        ON compliance_records(enterprise_id);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS compliance_records;")
