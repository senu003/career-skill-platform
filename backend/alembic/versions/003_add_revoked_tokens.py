"""Add revoked_tokens table for server-side token revocation.

Revision ID: 003_add_revoked_tokens
Revises: 002_add_question_review_fields
Create Date: 2026-11-06 02:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func

# revision identifiers, used by Alembic.
revision: str = '003_add_revoked_tokens'
down_revision: Union[str, None] = '002_add_question_review_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return insp.has_table(table_name)


def upgrade() -> None:
    if not _has_table("revoked_tokens"):
        op.create_table(
            "revoked_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("token_hash", sa.String(64), unique=True, index=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("expires_at", sa.DateTime(), index=True, nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=func.now()),
        )


def downgrade() -> None:
    if _has_table("revoked_tokens"):
        op.drop_table("revoked_tokens")
