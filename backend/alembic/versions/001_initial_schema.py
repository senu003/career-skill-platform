"""Initial schema baseline with full table definitions and telemetry columns.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-10-25 02:00:00

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import func, text

# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return insp.has_table(table_name)


def _has_column(table_name: str, column_name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table(table_name):
        return False
    columns = [c["name"] for c in insp.get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    # 1. users
    if not _has_table("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("email", sa.String(255), unique=True, nullable=False),
            sa.Column("password_hash", sa.Text(), nullable=True),
            sa.Column("avatar_url", sa.Text(), nullable=True),
            sa.Column("oauth_provider", sa.String(50), nullable=True),
            sa.Column("oauth_id", sa.String(255), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=text("TRUE")),
            sa.Column("created_at", sa.DateTime(), server_default=func.now()),
            sa.Column("updated_at", sa.DateTime(), server_default=func.now(), onupdate=func.now()),
        )
    else:
        # Verify OAuth columns exist
        if not _has_column("users", "avatar_url"):
            op.add_column("users", sa.Column("avatar_url", sa.Text(), nullable=True))
        if not _has_column("users", "oauth_provider"):
            op.add_column("users", sa.Column("oauth_provider", sa.String(50), nullable=True))
        if not _has_column("users", "oauth_id"):
            op.add_column("users", sa.Column("oauth_id", sa.String(255), nullable=True))
        if not _has_column("users", "is_active"):
            op.add_column("users", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=text("TRUE")))
        if not _has_column("users", "updated_at"):
            op.add_column("users", sa.Column("updated_at", sa.DateTime(), server_default=func.now()))

    # 2. password_reset_tokens
    if not _has_table("password_reset_tokens"):
        op.create_table(
            "password_reset_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("token_hash", sa.String(255), unique=True, nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used", sa.Boolean(), nullable=False, server_default=text("FALSE")),
            sa.Column("created_at", sa.DateTime(), server_default=func.now()),
        )

    # 3. security_audit_logs
    if not _has_table("security_audit_logs"):
        op.create_table(
            "security_audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
            sa.Column("event_type", sa.String(50), nullable=False),
            sa.Column("ip_address", sa.String(45), nullable=True),
            sa.Column("user_agent", sa.Text(), nullable=True),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=func.now()),
        )

    # 4. cvs
    if not _has_table("cvs"):
        op.create_table(
            "cvs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("file_name", sa.String(255), nullable=False),
            sa.Column("file_path", sa.Text(), nullable=False),
            sa.Column("uploaded_at", sa.DateTime(), server_default=func.now()),
        )

    # 5. skills
    if not _has_table("skills"):
        op.create_table(
            "skills",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(100), unique=True, nullable=False),
            sa.Column("category", sa.String(100), nullable=True),
        )

    # 6. cv_skills
    if not _has_table("cv_skills"):
        op.create_table(
            "cv_skills",
            sa.Column("cv_id", sa.Integer(), sa.ForeignKey("cvs.id"), primary_key=True),
            sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id"), primary_key=True),
            sa.Column("evidence", sa.Text(), nullable=True),
            sa.Column("confidence", sa.Numeric(5, 2), nullable=True),
        )

    # 7. jobs
    if not _has_table("jobs"):
        op.create_table(
            "jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("company", sa.String(200), nullable=True),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=func.now()),
        )

    # 8. job_skills
    if not _has_table("job_skills"):
        op.create_table(
            "job_skills",
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), primary_key=True),
            sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id"), primary_key=True),
            sa.Column("required_level", sa.String(50), nullable=True),
        )

    # 9. questions
    if not _has_table("questions"):
        op.create_table(
            "questions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id"), nullable=False),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("difficulty", sa.String(50), nullable=False),
            sa.Column("question_type", sa.String(50), nullable=False),
        )

    # 10. assessments
    if not _has_table("assessments"):
        op.create_table(
            "assessments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
            sa.Column("started_at", sa.DateTime(), server_default=func.now()),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )

    # 11. answers
    if not _has_table("answers"):
        op.create_table(
            "answers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("assessment_id", sa.Integer(), sa.ForeignKey("assessments.id"), nullable=False),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("questions.id"), nullable=False),
            sa.Column("answer", sa.Text(), nullable=True),
            sa.Column("is_correct", sa.Boolean(), nullable=True),
            sa.Column("score", sa.Numeric(5, 2), nullable=True),
        )

    # 12. analyses
    if not _has_table("analyses"):
        op.create_table(
            "analyses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("job_id", sa.Integer(), sa.ForeignKey("jobs.id"), nullable=False),
            sa.Column("cv_id", sa.Integer(), sa.ForeignKey("cvs.id"), nullable=False),
            sa.Column("overall_score", sa.Numeric(5, 2), nullable=True),
            sa.Column("raw_analysis_data", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=func.now()),
        )

    # 13. skill_analyses
    if not _has_table("skill_analyses"):
        op.create_table(
            "skill_analyses",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("analyses.id"), nullable=False),
            sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id"), nullable=False),
            sa.Column("cv_score", sa.Numeric(5, 2), nullable=True),
            sa.Column("assessment_score", sa.Numeric(5, 2), nullable=True),
            sa.Column("final_score", sa.Numeric(5, 2), nullable=True),
            sa.Column("gap_level", sa.String(50), nullable=True),
        )

    # 14. recommendations
    if not _has_table("recommendations"):
        op.create_table(
            "recommendations",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("analyses.id"), nullable=False),
            sa.Column("skill_id", sa.Integer(), sa.ForeignKey("skills.id"), nullable=False),
            sa.Column("recommendation", sa.Text(), nullable=False),
            sa.Column("priority", sa.String(50), nullable=True),
        )

    # 15. assessment_questions
    if not _has_table("assessment_questions"):
        op.create_table(
            "assessment_questions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("skill", sa.String(100), nullable=False),
            sa.Column("level", sa.String(20), nullable=False),
            sa.Column("topic", sa.String(100), nullable=True),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("correct_answer", sa.String(1), nullable=False),
            sa.Column("question_type", sa.String(50), nullable=False, server_default=text("'MCQ'")),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=text("TRUE")),
            sa.CheckConstraint("level IN ('basic', 'intermediate', 'advanced')", name="valid_question_level"),
            sa.CheckConstraint("correct_answer IN ('A', 'B', 'C', 'D')", name="valid_correct_answer"),
        )
    else:
        if not _has_column("assessment_questions", "question_type"):
            op.add_column("assessment_questions", sa.Column("question_type", sa.String(50), nullable=False, server_default=text("'MCQ'")))

    # 16. question_options
    if not _has_table("question_options"):
        op.create_table(
            "question_options",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("assessment_questions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("option_key", sa.String(1), nullable=False),
            sa.Column("option_text", sa.Text(), nullable=False),
            sa.CheckConstraint("option_key IN ('A', 'B', 'C', 'D')", name="valid_option_key"),
            sa.UniqueConstraint("question_id", "option_key", name="unique_question_option"),
        )

    # 17. assessment_attempts
    if not _has_table("assessment_attempts"):
        op.create_table(
            "assessment_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True),
            sa.Column("skill", sa.String(100), nullable=False),
            sa.Column("required_level", sa.String(20), nullable=False),
            sa.Column("cv_level", sa.String(20), nullable=True),
            sa.Column("assessed_level", sa.String(20), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False, server_default=func.now()),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
            sa.CheckConstraint("required_level IN ('basic', 'intermediate', 'advanced')", name="valid_required_level"),
            sa.CheckConstraint("cv_level IS NULL OR cv_level IN ('basic', 'intermediate', 'advanced')", name="valid_cv_level"),
            sa.CheckConstraint("assessed_level IS NULL OR assessed_level IN ('basic', 'intermediate', 'advanced')", name="valid_assessed_level"),
        )
    else:
        if not _has_column("assessment_attempts", "analysis_id"):
            op.add_column("assessment_attempts", sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("analyses.id", ondelete="SET NULL"), nullable=True))

    # 18. assessment_answers
    if not _has_table("assessment_answers"):
        op.create_table(
            "assessment_answers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("attempt_id", sa.Integer(), sa.ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("assessment_questions.id"), nullable=False),
            sa.Column("selected_answer", sa.String(1), nullable=False),
            sa.Column("is_correct", sa.Boolean(), nullable=False),
            sa.Column("time_taken", sa.Numeric(8, 2), nullable=True),
            sa.Column("answered_at", sa.DateTime(), nullable=False, server_default=func.now()),
            sa.CheckConstraint("selected_answer IN ('A', 'B', 'C', 'D')", name="valid_selected_answer"),
            sa.UniqueConstraint("attempt_id", "question_id", name="unique_attempt_question"),
        )
    else:
        if not _has_column("assessment_answers", "time_taken"):
            op.add_column("assessment_answers", sa.Column("time_taken", sa.Numeric(8, 2), nullable=True))


def downgrade() -> None:
    # Drop tables in reverse topological order
    tables = [
        "assessment_answers",
        "assessment_attempts",
        "question_options",
        "assessment_questions",
        "recommendations",
        "skill_analyses",
        "analyses",
        "answers",
        "assessments",
        "questions",
        "job_skills",
        "jobs",
        "cv_skills",
        "skills",
        "cvs",
        "security_audit_logs",
        "password_reset_tokens",
        "users",
    ]
    for tbl in tables:
        if _has_table(tbl):
            op.drop_table(tbl)
