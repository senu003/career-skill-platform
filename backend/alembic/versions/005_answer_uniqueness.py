"""Ensure assessment_answers uniqueness constraint and deduplicate existing records.

Revision ID: 005_answer_uniqueness
Revises: 004_add_analysis_requests
Create Date: 2026-11-07 00:30:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic (must be <= 32 chars)
revision: str = '005_answer_uniqueness'
down_revision: Union[str, None] = '004_add_analysis_requests'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("assessment_answers"):
        # 1. Deduplicate any existing duplicate answers keeping the latest record (max id)
        bind.execute(sa.text("""
            DELETE FROM assessment_answers
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM assessment_answers
                GROUP BY attempt_id, question_id
            )
        """))

        # 2. Check existing unique constraints or indexes
        existing_ucs = [uc["name"] for uc in insp.get_unique_constraints("assessment_answers") if uc.get("name")]
        existing_indexes = [idx["name"] for idx in insp.get_indexes("assessment_answers") if idx.get("name")]

        if "unique_attempt_question" not in existing_ucs and "unique_attempt_question" not in existing_indexes:
            try:
                op.create_unique_constraint(
                    "unique_attempt_question",
                    "assessment_answers",
                    ["attempt_id", "question_id"]
                )
            except Exception:
                # Fallback for dialects where unique constraint creation syntax varies
                pass


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("assessment_answers"):
        existing_ucs = [uc["name"] for uc in insp.get_unique_constraints("assessment_answers") if uc.get("name")]
        if "unique_attempt_question" in existing_ucs:
            try:
                op.drop_constraint("unique_attempt_question", "assessment_answers", type_="unique")
            except Exception:
                pass

