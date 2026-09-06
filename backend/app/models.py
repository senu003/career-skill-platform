from sqlalchemy import (
    Column, Integer, String, Text, Boolean,
    DateTime, Numeric, ForeignKey, CheckConstraint, UniqueConstraint, text
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class CV(Base):
    __tablename__ = "cvs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    uploaded_at = Column(DateTime, server_default=func.now())


class Skill(Base):
    __tablename__ = "skills"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    category = Column(String(100))


class CVSkill(Base):
    __tablename__ = "cv_skills"

    cv_id = Column(Integer, ForeignKey("cvs.id"), primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), primary_key=True)
    evidence = Column(Text)
    confidence = Column(Numeric(5, 2))


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    title = Column(String(200), nullable=False)
    company = Column(String(200))
    description = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class JobSkill(Base):
    __tablename__ = "job_skills"

    job_id = Column(Integer, ForeignKey("jobs.id"), primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), primary_key=True)
    required_level = Column(String(50))


class Question(Base):
    __tablename__ = "questions"

    id = Column(Integer, primary_key=True)
    skill_id = Column(Integer, ForeignKey("skills.id"), nullable=False)
    question_text = Column(Text, nullable=False)
    difficulty = Column(String(50), nullable=False)
    question_type = Column(String(50), nullable=False)


class Assessment(Base):
    __tablename__ = "assessments"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    started_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)


class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True)
    assessment_id = Column(
        Integer,
        ForeignKey("assessments.id"),
        nullable=False
    )
    question_id = Column(
        Integer,
        ForeignKey("questions.id"),
        nullable=False
    )
    answer = Column(Text)
    is_correct = Column(Boolean)
    score = Column(Numeric(5, 2))


class Analysis(Base):
    __tablename__ = "analyses"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    cv_id = Column(Integer, ForeignKey("cvs.id"), nullable=False)
    overall_score = Column(Numeric(5, 2))
    created_at = Column(DateTime, server_default=func.now())


class SkillAnalysis(Base):
    __tablename__ = "skill_analyses"

    id = Column(Integer, primary_key=True)
    analysis_id = Column(
        Integer,
        ForeignKey("analyses.id"),
        nullable=False
    )
    skill_id = Column(
        Integer,
        ForeignKey("skills.id"),
        nullable=False
    )
    cv_score = Column(Numeric(5, 2))
    assessment_score = Column(Numeric(5, 2))
    final_score = Column(Numeric(5, 2))
    gap_level = Column(String(50))


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True)
    analysis_id = Column(
        Integer,
        ForeignKey("analyses.id"),
        nullable=False
    )
    skill_id = Column(
        Integer,
        ForeignKey("skills.id"),
        nullable=False
    )
    recommendation = Column(Text, nullable=False)
    priority = Column(String(50))


class AssessmentQuestion(Base):
    __tablename__ = "assessment_questions"

    id = Column(Integer, primary_key=True)
    skill = Column(String(100), nullable=False)
    level = Column(String(20), nullable=False)
    topic = Column(String(100))
    question = Column(Text, nullable=False)
    correct_answer = Column(String(1), nullable=False)
    question_type = Column(String(50), nullable=False, default="MCQ", server_default=text("'MCQ'"))
    is_active = Column(Boolean, nullable=False, default=True, server_default=text("TRUE"))

    options = relationship("QuestionOption", back_populates="question_obj", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("level IN ('basic', 'intermediate', 'advanced')", name="valid_question_level"),
        CheckConstraint("correct_answer IN ('A', 'B', 'C', 'D')", name="valid_correct_answer"),
    )


class QuestionOption(Base):
    __tablename__ = "question_options"

    id = Column(Integer, primary_key=True)
    question_id = Column(
        Integer,
        ForeignKey("assessment_questions.id", ondelete="CASCADE"),
        nullable=False
    )
    option_key = Column(String(1), nullable=False)
    option_text = Column(Text, nullable=False)

    question_obj = relationship("AssessmentQuestion", back_populates="options")

    __table_args__ = (
        CheckConstraint("option_key IN ('A', 'B', 'C', 'D')", name="valid_option_key"),
        UniqueConstraint("question_id", "option_key", name="unique_question_option"),
    )


class AssessmentAttempt(Base):
    __tablename__ = "assessment_attempts"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)
    skill = Column(String(100), nullable=False)
    required_level = Column(String(20), nullable=False)
    cv_level = Column(String(20), nullable=True)
    assessed_level = Column(String(20), nullable=True)
    started_at = Column(DateTime, nullable=False, server_default=func.now())
    completed_at = Column(DateTime, nullable=True)

    answers = relationship("AssessmentAnswer", back_populates="attempt", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("required_level IN ('basic', 'intermediate', 'advanced')", name="valid_required_level"),
        CheckConstraint("cv_level IS NULL OR cv_level IN ('basic', 'intermediate', 'advanced')", name="valid_cv_level"),
        CheckConstraint("assessed_level IS NULL OR assessed_level IN ('basic', 'intermediate', 'advanced')", name="valid_assessed_level"),
    )


class AssessmentAnswer(Base):
    __tablename__ = "assessment_answers"

    id = Column(Integer, primary_key=True)
    attempt_id = Column(
        Integer,
        ForeignKey("assessment_attempts.id", ondelete="CASCADE"),
        nullable=False
    )
    question_id = Column(
        Integer,
        ForeignKey("assessment_questions.id"),
        nullable=False
    )
    selected_answer = Column(String(1), nullable=False)
    is_correct = Column(Boolean, nullable=False)
    time_taken = Column(Numeric(8, 2), nullable=True)
    answered_at = Column(DateTime, nullable=False, server_default=func.now())

    attempt = relationship("AssessmentAttempt", back_populates="answers")
    question_obj = relationship("AssessmentQuestion")

    __table_args__ = (
        CheckConstraint("selected_answer IN ('A', 'B', 'C', 'D')", name="valid_selected_answer"),
        UniqueConstraint("attempt_id", "question_id", name="unique_attempt_question"),
    )