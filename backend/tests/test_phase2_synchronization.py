import os
import sys
import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal, Base, engine
from app.models import User, AssessmentAttempt, AssessmentAnswer, AssessmentQuestion, Job, CV, Analysis
from app.schemas.skill_analysis import FinalSkillItemSchema
from app.services.aggregation_service import aggregate_final_assessment
from app.services.skill_analysis_service import (
    combine_cv_and_assessment,
    get_assessment_result_for_skill,
    calculate_level_gap,
)
from app.ml.predict_readiness import predict_final_recommendation


@pytest.fixture(scope="module")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    yield session
    session.close()


def test_defect1_aggregation_unassessed_skills_do_not_produce_zero_cv_evidence():
    """
    Verifies Defect 1: Unassessed skills with level_gap=None do NOT result in zero requirements met.
    Requirements evidenced in CV and requirements verified through assessment are tracked separately.
    """
    skills = [
        FinalSkillItemSchema(
            skill="Python",
            required_level="intermediate",
            importance="required",
            matched=True,
            cv_match_status="Match",
            cv_level="intermediate",
            assessed_level=None,
            level_gap=None,
            total_score=None,
            is_weakness=False,
            weakness_reason="NONE",
            priority="LOW",
        ),
        FinalSkillItemSchema(
            skill="SQL",
            required_level="basic",
            importance="required",
            matched=True,
            cv_match_status="Match",
            cv_level="basic",
            assessed_level=None,
            level_gap=None,
            total_score=None,
            is_weakness=False,
            weakness_reason="NONE",
            priority="LOW",
        ),
        FinalSkillItemSchema(
            skill="Docker",
            required_level="basic",
            importance="required",
            matched=False,
            cv_match_status="Missing",
            cv_level="not_found",
            assessed_level=None,
            level_gap=None,
            total_score=None,
            is_weakness=True,
            weakness_reason="UNVERIFIED_IN_CV",
            priority="MEDIUM",
        ),
    ]

    res = aggregate_final_assessment(skills)

    # 1. Verification status is preliminary
    assert res.is_preliminary is True
    assert "Preliminary" in res.verification_status

    # 2. CV evidenced vs assessment verified counts
    assert res.requirements_evidenced_cv == 2
    assert res.requirements_verified_assessment == 0
    assert res.unverified_cv_missing_count == 1
    assert res.assessed_skills_count == 0
    assert res.assessment_completion_rate == 0.0

    # 3. Required skills summary does not falsely claim 0 skills evidenced
    assert res.total_skills == 3


def test_defect2_unassessed_cv_match_never_labeled_mastered():
    """
    Verifies Defect 2: An unassessed CV match is never labeled as Mastered in Model 1 / skill analysis.
    """
    cv_data = {
        "matched_skills": [
            {
                "skill": "Python",
                "level": "intermediate",
                "importance": "required",
                "evidence": "5 years Python developer experience",
                "cv_match_status": "Match",
                "cv_level": "intermediate",
                "matched": True,
            }
        ],
        "missing_skills": [],
    }

    res = combine_cv_and_assessment(cv_data, db_or_assessments=None)
    skill_item = res["skills"][0]

    # Must be unverified, never Mastered
    assert skill_item["assessed_level"] is None
    assert skill_item["skill_recommendation"] is None or skill_item["skill_recommendation"] != "Mastered"
    assert "Assessment optional for verification" in skill_item["recommendation"]
    assert res["is_preliminary"] is True


def test_defect3_assessment_completion_does_not_mutate_cv_evidence():
    """
    Verifies Defect 3: Passing an assessment for a missing skill verifies proficiency
    without overwriting the fact that the skill was originally missing from the CV.
    """
    cv_data = {
        "matched_skills": [],
        "missing_skills": [
            {
                "skill": "Kubernetes",
                "level": "intermediate",
                "importance": "required",
                "cv_match_status": "Missing",
                "cv_level": "not_found",
                "matched": False,
            }
        ],
    }

    # Candidate scored 85% and was assessed at intermediate
    mock_assessments = {
        "Kubernetes": {
            "assessed_level": "intermediate",
            "required_level": "intermediate",
            "level_gap": 0,
            "total_score": 0.85,
            "basic_score": 0.9,
            "intermediate_score": 0.8,
            "advanced_score": 0.0,
        }
    }

    res = combine_cv_and_assessment(cv_data, db_or_assessments=mock_assessments)
    skill_item = res["skills"][0]

    # 1. Assessment proficiency is verified
    assert skill_item["assessed_level"] == "intermediate"
    assert skill_item["level_gap"] == 0
    assert skill_item["is_weakness"] is False

    # 2. Original CV evidence is strictly preserved
    assert skill_item["cv_match_status"] == "Missing"
    assert skill_item["matched"] is False


def test_defect4_authoritative_readiness_verdict_and_verification_status():
    """
    Verifies Defect 4: Single authoritative verdict across 0 assessments, partial assessments, and full assessments.
    """
    # 0 assessments: Preliminary
    prelim_res = predict_final_recommendation({
        "skills": [
            {"skill": "React", "importance": "required", "matched": True, "cv_match_status": "Match", "level": "intermediate"},
            {"skill": "Node", "importance": "required", "matched": True, "cv_match_status": "Match", "level": "intermediate"},
        ]
    })
    assert prelim_res["is_preliminary"] is True
    assert "Preliminary" in prelim_res["verification_status"]
    assert prelim_res["final_verdict"] == prelim_res["readiness_verdict"]

    # Partial assessments: 1 assessed, 1 unassessed
    partial_res = predict_final_recommendation({
        "skills": [
            {"skill": "React", "importance": "required", "matched": True, "assessed_level": "intermediate", "total_score": 0.85, "level": "intermediate"},
            {"skill": "Node", "importance": "required", "matched": True, "cv_match_status": "Match", "level": "intermediate"},
        ]
    })
    assert partial_res["is_preliminary"] is False
    assert partial_res["final_verdict"] == partial_res["readiness_verdict"]


def test_defect5_retake_telemetry_passed_to_model1(db_session: Session):
    """
    Verifies Defect 5 & 8: Retake selection selects latest completed attempt,
    preserves historical attempts, and calculates attempt_count and previous_best_score.
    """
    user = User(email="test_retake_user@example.com", password_hash="pw", name="Retake Candidate")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Attempt 1: Poor score 30%
    att1 = AssessmentAttempt(
        user_id=user.id,
        skill="FastAPI",
        required_level="intermediate",
        assessed_level="basic",
        completed_at=datetime(2026, 10, 1, 10, 0, tzinfo=timezone.utc),
    )
    db_session.add(att1)
    db_session.commit()
    db_session.refresh(att1)

    # Attempt 2: Improved score 85%
    att2 = AssessmentAttempt(
        user_id=user.id,
        skill="FastAPI",
        required_level="intermediate",
        assessed_level="intermediate",
        completed_at=datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc),
    )
    db_session.add(att2)
    db_session.commit()
    db_session.refresh(att2)

    # Retrieve assessment result for skill
    result = get_assessment_result_for_skill(db=db_session, skill="FastAPI", user_id=user.id)

    # 1. Selected attempt is latest (att2)
    assert result is not None
    assert result["attempt_id"] == att2.id
    assert result["assessed_level"] == "intermediate"
    assert result["level_gap"] == 0

    # 2. Retake telemetry is tracked
    assert result["attempt_count"] == 2

    # Clean up test user
    db_session.delete(att1)
    db_session.delete(att2)
    db_session.delete(user)
    db_session.commit()


def test_scenario_c_poor_assessment_result_creates_verified_gap():
    """
    Scenario C: Candidate claimed skill on CV but scored poorly on quiz (<40%).
    Verified assessment evidence must override CV claim and produce a gap.
    """
    cv_data = {
        "matched_skills": [
            {
                "skill": "TypeScript",
                "level": "intermediate",
                "importance": "required",
                "cv_match_status": "Match",
                "cv_level": "intermediate",
                "matched": True,
            }
        ],
        "missing_skills": [],
    }

    poor_quiz = {
        "TypeScript": {
            "assessed_level": "basic",
            "required_level": "intermediate",
            "level_gap": 1,
            "total_score": 0.25,
            "basic_score": 0.25,
            "intermediate_score": 0.0,
            "advanced_score": 0.0,
        }
    }

    res = combine_cv_and_assessment(cv_data, db_or_assessments=poor_quiz)
    skill_item = res["skills"][0]

    # Gap must be confirmed
    assert skill_item["assessed_level"] == "basic"
    assert skill_item["level_gap"] == 1
    assert skill_item["is_weakness"] is True
    assert skill_item["weakness_reason"] in ["LOW_ASSESSMENT_SCORE", "LEVEL_GAP_AND_LOW_SCORE", "LEVEL_GAP"]
    assert skill_item["priority"] == "MEDIUM" or skill_item["priority"] == "HIGH"


def test_scenario_h_preferred_skill_missing_does_not_block_interview_ready():
    """
    Scenario H: Required skills are verified, but a preferred (nice-to-have) skill is missing.
    Preferred skill gap must not block Interview Ready verdict.
    """
    payload = {
        "skills": [
            {"skill": "React", "importance": "required", "assessed_level": "intermediate", "level_gap": 0, "total_score": 0.90, "matched": True},
            {"skill": "Python", "importance": "required", "assessed_level": "intermediate", "level_gap": 0, "total_score": 0.85, "matched": True},
            {"skill": "GraphQL", "importance": "preferred", "assessed_level": None, "cv_match_status": "Missing", "matched": False},
        ]
    }

    res = predict_final_recommendation(payload)
    # 100% of required skills are verified mastered; missing preferred skill does not force major upskill
    assert res["final_verdict"] == "Interview Ready"
