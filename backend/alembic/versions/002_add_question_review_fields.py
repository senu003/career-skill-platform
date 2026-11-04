"""Add question review explanation and interview tip fields.

Revision ID: 002_add_question_review_fields
Revises: 001_initial_schema
Create Date: 2026-10-25 15:30:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002_add_question_review_fields'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table(table_name):
        return False
    columns = [c["name"] for c in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    if not _has_column("assessment_questions", "explanation"):
        op.add_column("assessment_questions", sa.Column("explanation", sa.Text(), nullable=True))

    if not _has_column("assessment_questions", "misconception"):
        op.add_column("assessment_questions", sa.Column("misconception", sa.Text(), nullable=True))

    if not _has_column("assessment_questions", "interview_tip"):
        op.add_column("assessment_questions", sa.Column("interview_tip", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column("assessment_questions", "interview_tip"):
        op.drop_column("assessment_questions", "interview_tip")

    if _has_column("assessment_questions", "misconception"):
        op.drop_column("assessment_questions", "misconception")

    if _has_column("assessment_questions", "explanation"):
        op.drop_column("assessment_questions", "explanation")
