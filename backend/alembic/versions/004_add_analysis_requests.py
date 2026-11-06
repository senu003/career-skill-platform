"""Add analysis_requests table for atomic CV analysis writes and safe retries.

Revision ID: 004_add_analysis_requests
Revises: 003_add_revoked_tokens
Create Date: 2026-11-06 11:30:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = '004_add_analysis_requests'
down_revision: Union[str, None] = '003_add_revoked_tokens'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return insp.has_table(table_name)


def upgrade() -> None:
    if not _has_table("analysis_requests"):
        op.create_table(
            "analysis_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("idempotency_key", sa.String(128), nullable=False, index=True),
            sa.Column("request_hash", sa.String(64), nullable=False),
            sa.Column("status", sa.String(32), nullable=False, server_default=sa.text("'processing'")),
            sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True),
            sa.Column("response_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=func.now()),
            sa.UniqueConstraint("user_id", "idempotency_key", name="uq_analysis_requests_user_key"),
        )


def downgrade() -> None:
    if _has_table("analysis_requests"):
        op.drop_table("analysis_requests")

