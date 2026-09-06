import pytest
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models import AssessmentAttempt
from app.services.skill_analysis_service import get_assessment_result_for_skill
from app.services.longitudinal_service import get_candidate_history
from app.database import SessionLocal

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        # Rollback and clean up in tests if needed, or let them commit
        # Actually since tests commit, we might want to clean up manually or let the test DB persist (if it's a test db).
        # We'll just close it.
        db.close()


def test_guest_history_lookup_bug(db_session: Session):
    """Ensure user_id=None returns None instead of finding the latest attempt system-wide."""
    # Create an attempt for an actual user
    attempt = AssessmentAttempt(
        user_id=999,
        skill="Python",
        required_level="intermediate",
        assessed_level="basic",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc)
    )
    db_session.add(attempt)
    db_session.commit()
    
    # Query with user_id=None (Guest)
    res = get_assessment_result_for_skill(db_session, "Python", user_id=None)
    assert res is None, "Guest query leaked another user's attempt!"

def test_longitudinal_history_different_users(db_session: Session):
    """Ensure attempts for different users do not pair."""
    db_session.query(AssessmentAttempt).filter(AssessmentAttempt.user_id.in_([1001, 1002])).delete()
    db_session.commit()
    for uid in [1001, 1002]:
        attempt = AssessmentAttempt(
            user_id=uid,
            skill="React",
            required_level="intermediate",
            assessed_level="basic",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc)
        )
        db_session.add(attempt)
    db_session.commit()
    
    history1 = get_candidate_history(db_session, 1001)
    history2 = get_candidate_history(db_session, 1002)
    
    assert len(history1["react"]) == 1
    assert len(history2["react"]) == 1

def test_longitudinal_outcome_improvement(db_session: Session, monkeypatch):
    """Test longitudinal outcome with score and level improvement."""
    user_id = 42
    db_session.query(AssessmentAttempt).filter(AssessmentAttempt.user_id == user_id).delete()
    db_session.commit()
    skill = "javascript"
    
    # Attempt 1
    a1 = AssessmentAttempt(
        user_id=user_id,
        skill=skill,
        required_level="advanced",
        assessed_level="basic",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc)
    )
    db_session.add(a1)
    db_session.commit()
    
    # Attempt 2
    a2 = AssessmentAttempt(
        user_id=user_id,
        skill=skill,
        required_level="advanced",
        assessed_level="intermediate",
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc)
    )
    db_session.add(a2)
    db_session.commit()
    
    # Mock extract_assessment_scores to simulate scores
    def mock_extract(db, data):
        if data["attempt_id"] == a1.id:
            return {"basic_score": 0.8, "intermediate_score": 0.2, "advanced_score": 0.0, "total_score": 0.36}
        else:
            return {"basic_score": 1.0, "intermediate_score": 0.8, "advanced_score": 0.2, "total_score": 0.72}
            
    monkeypatch.setattr("app.services.longitudinal_service.extract_assessment_scores", mock_extract)
    
    history = get_candidate_history(db_session, user_id)
    obs_list = history[skill]
    assert len(obs_list) == 2
    
    # Check first attempt has no outcome
    assert obs_list[0]["outcome"] is None
    
    # Check second attempt outcome
    outcome = obs_list[1]["outcome"]
    assert outcome is not None
    assert outcome["score_change"] > 0
    assert outcome["level_change"] == 1
    assert outcome["improved"] is True
    assert outcome["declined"] is False

def test_longitudinal_outcome_decline(db_session: Session, monkeypatch):
    """Test longitudinal outcome with score decline."""
    user_id = 43
    db_session.query(AssessmentAttempt).filter(AssessmentAttempt.user_id == user_id).delete()
    db_session.commit()
    skill = "postgresql"
    
    a1 = AssessmentAttempt(user_id=user_id, skill=skill, required_level="intermediate", assessed_level="intermediate", started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc))
    a2 = AssessmentAttempt(user_id=user_id, skill=skill, required_level="intermediate", assessed_level="basic", started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc))
    db_session.add_all([a1, a2])
    db_session.commit()
    
    monkeypatch.setattr("app.services.longitudinal_service.extract_assessment_scores", lambda db, d: {"basic_score": 0, "intermediate_score": 0, "advanced_score": 0, "total_score": 0.8} if d["attempt_id"] == a1.id else {"basic_score": 0, "intermediate_score": 0, "advanced_score": 0, "total_score": 0.4})
    
    history = get_candidate_history(db_session, user_id)
    outcome = history[skill][1]["outcome"]
    
    assert outcome["level_change"] == -1
    assert round(outcome["score_change"], 2) == -0.40
    assert outcome["declined"] is True
    assert outcome["improved"] is False

def test_persistent_weakness(db_session: Session, monkeypatch):
    """Test persistent weakness detection."""
    user_id = 44
    db_session.query(AssessmentAttempt).filter(AssessmentAttempt.user_id == user_id).delete()
    db_session.commit()
    skill = "react"
    
    a1 = AssessmentAttempt(user_id=user_id, skill=skill, required_level="advanced", assessed_level="basic", started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc))
    a2 = AssessmentAttempt(user_id=user_id, skill=skill, required_level="advanced", assessed_level="basic", started_at=datetime.now(timezone.utc), completed_at=datetime.now(timezone.utc))
    db_session.add_all([a1, a2])
    db_session.commit()
    
    monkeypatch.setattr("app.services.longitudinal_service.extract_assessment_scores", lambda db, d: {"basic_score": 0, "intermediate_score": 0, "advanced_score": 0, "total_score": 0.4})
    
    history = get_candidate_history(db_session, user_id)
    
    obs1 = history[skill][0]
    obs2 = history[skill][1]
    
    assert obs1["is_weakness"] is True
    assert obs2["is_weakness"] is True
    assert obs2["outcome"]["persistent_weakness"] is True

def test_guest_returns_empty_history(db_session: Session):
    assert get_candidate_history(db_session, None) == {}
