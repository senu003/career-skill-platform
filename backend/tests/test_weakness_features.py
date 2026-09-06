"""
Unit tests for Weakness ML Feature Extraction (app/ml/weakness_features.py)
"""

from datetime import datetime, timezone, timedelta
import pytest
from app.ml.weakness_features import build_weakness_features, FEATURE_KEYS


def test_1_one_assessed_skill():
    """Test 1: Extract features for a single assessed skill."""
    attempt = {
        "skill": "JavaScript",
        "required_level": "advanced",  # 3
        "assessed_level": "intermediate",  # 2
        "answers": [
            {
                "level": "basic",
                "is_correct": True,
                "answered_at": "2026-08-30T10:00:00Z"
            },
            {
                "level": "basic",
                "is_correct": True,
                "answered_at": "2026-08-30T10:00:10Z"
            }
        ]
    }
    feats = build_weakness_features([attempt])
    assert len(feats) == 1
    item = feats[0]
    assert item["skill"] == "JavaScript"
    assert item["required_level"] == 3
    assert item["assessed_level"] == 2
    assert item["level_gap"] == 1
    assert item["questions_answered_count"] == 2


def test_2_multiple_assessed_skills():
    """Test 2: Extract features for multiple assessed skills."""
    attempts = [
        {"skill": "JavaScript", "required_level": "advanced", "assessed_level": "advanced", "total_score": 1.0},
        {"skill": "React", "required_level": "intermediate", "assessed_level": "basic", "total_score": 0.5},
        {"skill": "PostgreSQL", "required_level": "basic", "assessed_level": "basic", "total_score": 0.8}
    ]
    feats = build_weakness_features(attempts)
    assert len(feats) == 3
    assert [f["skill"] for f in feats] == ["JavaScript", "React", "PostgreSQL"]


def test_3_correct_level_gap_calculation():
    """Test 3: Correct level-gap calculation using numeric values."""
    attempts = [
        {"skill": "JS", "required_level": "advanced", "assessed_level": "basic"},        # 3 - 1 = 2
        {"skill": "React", "required_level": "intermediate", "assessed_level": None},    # 2 - 0 = 2
        {"skill": "SQL", "required_level": "basic", "assessed_level": "advanced"}        # max(0, 1 - 3) = 0
    ]
    feats = build_weakness_features(attempts)
    assert feats[0]["level_gap"] == 2
    assert feats[1]["level_gap"] == 2
    assert feats[2]["level_gap"] == 0


def test_4_correct_score_extraction():
    """Test 4: Correct score extraction across levels and total."""
    attempt = {
        "skill": "JavaScript",
        "required_level": "advanced",
        "assessed_level": "intermediate",
        "answers": [
            {"level": "basic", "is_correct": True},
            {"level": "basic", "is_correct": True},
            {"level": "basic", "is_correct": True},
            {"level": "basic", "is_correct": True},
            {"level": "basic", "is_correct": True},
            {"level": "intermediate", "is_correct": True},
            {"level": "intermediate", "is_correct": True},
            {"level": "intermediate", "is_correct": True},
            {"level": "intermediate", "is_correct": True},
            {"level": "intermediate", "is_correct": False},
        ]
    }
    feats = build_weakness_features([attempt])
    item = feats[0]
    assert item["basic_score"] == 1.0          # 5/5
    assert item["intermediate_score"] == 0.8   # 4/5
    assert item["advanced_score"] == 0.0       # 0/5
    assert item["total_score"] == 0.9          # 9/10
    assert item["questions_answered_count"] == 10


def test_5_correct_average_answer_time_calculation():
    """Test 5: Correct average answer-time calculation from consecutive timestamps."""
    t0 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)
    t1 = t0 + timedelta(seconds=10)
    t2 = t1 + timedelta(seconds=20)
    t3 = t2 + timedelta(seconds=30)

    attempt = {
        "skill": "React",
        "required_level": "intermediate",
        "assessed_level": "intermediate",
        "answers": [
            {"level": "basic", "is_correct": True, "answered_at": t0.isoformat()},
            {"level": "basic", "is_correct": True, "answered_at": t1.isoformat()},
            {"level": "basic", "is_correct": True, "answered_at": t2.isoformat()},
            {"level": "basic", "is_correct": True, "answered_at": t3.isoformat()},
        ]
    }
    feats = build_weakness_features([attempt])
    item = feats[0]
    # Intervals: 10s, 20s, 30s -> mean = 20.0
    assert item["timed_questions_count"] == 3
    assert item["avg_answer_time_seconds"] == 20.0
    assert item["min_answer_time_seconds"] == 10.0
    assert item["max_answer_time_seconds"] == 30.0


def test_6_correct_timing_standard_deviation():
    """Test 6: Correct timing standard deviation calculation."""
    t0 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc)
    # Intervals: 10s, 10s, 10s -> std = 0.0
    t1 = t0 + timedelta(seconds=10)
    t2 = t1 + timedelta(seconds=10)
    t3 = t2 + timedelta(seconds=10)

    attempt = {
        "skill": "Python",
        "required_level": "basic",
        "assessed_level": "basic",
        "answers": [
            {"level": "basic", "is_correct": True, "answered_at": t0.isoformat()},
            {"level": "basic", "is_correct": True, "answered_at": t1.isoformat()},
            {"level": "basic", "is_correct": True, "answered_at": t2.isoformat()},
            {"level": "basic", "is_correct": True, "answered_at": t3.isoformat()},
        ]
    }
    feats = build_weakness_features([attempt])
    assert feats[0]["answer_time_std_seconds"] == 0.0


def test_7_missing_timestamps():
    """Test 7: Missing timestamps handled safely."""
    attempt = {
        "skill": "SQL",
        "required_level": "basic",
        "assessed_level": "basic",
        "answers": [
            {"level": "basic", "is_correct": True, "answered_at": None},
            {"level": "basic", "is_correct": True, "answered_at": ""},
        ]
    }
    feats = build_weakness_features([attempt])
    item = feats[0]
    assert item["timed_questions_count"] == 0
    assert item["avg_answer_time_seconds"] == 0.0
    assert item["answer_time_std_seconds"] == 0.0


def test_8_single_answer_case():
    """Test 8: Single-answer case (no consecutive intervals)."""
    attempt = {
        "skill": "Docker",
        "required_level": "basic",
        "assessed_level": "basic",
        "answers": [
            {"level": "basic", "is_correct": True, "answered_at": "2026-08-30T10:00:00Z"}
        ]
    }
    feats = build_weakness_features([attempt])
    item = feats[0]
    assert item["timed_questions_count"] == 0
    assert item["avg_answer_time_seconds"] == 0.0
    assert item["questions_answered_count"] == 1


def test_9_duplicate_timestamps():
    """Test 9: Duplicate timestamps (interval = 0.0 seconds)."""
    t0 = "2026-08-30T10:00:00Z"
    attempt = {
        "skill": "Git",
        "required_level": "basic",
        "assessed_level": "basic",
        "answers": [
            {"level": "basic", "is_correct": True, "answered_at": t0},
            {"level": "basic", "is_correct": True, "answered_at": t0},
        ]
    }
    feats = build_weakness_features([attempt])
    item = feats[0]
    assert item["timed_questions_count"] == 1
    assert item["avg_answer_time_seconds"] == 0.0
    assert item["min_answer_time_seconds"] == 0.0


def test_10_negative_timestamp_handling():
    """Test 10: Negative timestamp differences ignored cleanly."""
    t0 = datetime(2026, 8, 30, 10, 0, 10, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 30, 10, 0, 5, tzinfo=timezone.utc)  # -5 seconds, invalid

    attempt = {
        "skill": "Linux",
        "required_level": "basic",
        "assessed_level": "basic",
        "answers": [
            {"level": "basic", "is_correct": True, "answered_at": t0.isoformat()},
            {"level": "basic", "is_correct": True, "answered_at": t1.isoformat()},
        ]
    }
    feats = build_weakness_features([attempt])
    item = feats[0]
    # Negative interval should be ignored
    assert item["timed_questions_count"] == 0
    assert item["avg_answer_time_seconds"] == 0.0


def test_11_candidate_level_average_score():
    """Test 11: Candidate-level average score across assessed skills."""
    attempts = [
        {"skill": "JS", "required_level": "basic", "assessed_level": "basic", "total_score": 1.0},
        {"skill": "React", "required_level": "basic", "assessed_level": "basic", "total_score": 0.8},
        {"skill": "Node", "required_level": "basic", "assessed_level": "basic", "total_score": 0.6},
    ]
    feats = build_weakness_features(attempts)
    # Mean total score = (1.0 + 0.8 + 0.6) / 3 = 0.8
    for item in feats:
        assert item["candidate_avg_total_score"] == 0.8


def test_12_candidate_below_requirement_ratio():
    """Test 12: Candidate below-requirement ratio."""
    attempts = [
        {"skill": "JS", "required_level": "advanced", "assessed_level": "advanced"},    # gap = 0
        {"skill": "React", "required_level": "advanced", "assessed_level": "basic"},   # gap = 2
        {"skill": "SQL", "required_level": "intermediate", "assessed_level": "basic"}, # gap = 1
    ]
    feats = build_weakness_features(attempts)
    # 2 out of 3 skills have gap > 0 -> ratio = 2/3 = 0.6667
    for item in feats:
        assert item["candidate_below_requirement_ratio"] == pytest.approx(0.6667, abs=1e-4)


def test_13_multiple_skills_with_different_performance():
    """Test 13: Multiple skills with different performance levels."""
    attempts = [
        {
            "skill": "JS",
            "required_level": "advanced",
            "assessed_level": "advanced",
            "basic_score": 1.0,
            "intermediate_score": 1.0,
            "advanced_score": 1.0,
            "total_score": 1.0
        },
        {
            "skill": "Python",
            "required_level": "advanced",
            "assessed_level": None,
            "basic_score": 0.2,
            "intermediate_score": 0.0,
            "advanced_score": 0.0,
            "total_score": 0.2
        }
    ]
    feats = build_weakness_features(attempts)
    assert len(feats) == 2
    assert feats[0]["level_gap"] == 0
    assert feats[1]["level_gap"] == 3
    assert feats[0]["candidate_avg_total_score"] == 0.6
    assert feats[0]["candidate_score_std"] == 0.4


def test_14_empty_input():
    """Test 14: Empty input returns empty list."""
    assert build_weakness_features([]) == []
    assert build_weakness_features(None) == []


def test_15_verify_no_prediction_or_priority_label():
    """Test 15: Verify no prediction or priority label is produced."""
    attempt = {
        "skill": "JavaScript",
        "required_level": "advanced",
        "assessed_level": "basic",
        "total_score": 0.2
    }
    feats = build_weakness_features([attempt])
    item = feats[0]

    forbidden_keys = [
        "priority",
        "improvement_needed",
        "improvement_probability",
        "predicted_label",
        "readiness_score",
        "risk_level"
    ]
    for key in forbidden_keys:
        assert key not in item


def test_16_verify_feature_keys_fixed_and_consistent():
    """Test 16: Verify the output feature keys are fixed and consistent."""
    attempt = {
        "skill": "JavaScript",
        "required_level": "intermediate",
        "assessed_level": "basic",
        "total_score": 0.7
    }
    feats = build_weakness_features([attempt])
    item = feats[0]

    assert list(item.keys()) == FEATURE_KEYS
    assert len(item.keys()) == 18


def test_17_verify_no_future_reassessment_fields():
    """Test 17: Verify no future or reassessment fields are accepted or present."""
    attempt = {
        "skill": "JavaScript",
        "required_level": "intermediate",
        "assessed_level": "basic",
        "total_score": 0.7,
        # Intentionally include future leakage fields in input
        "t2_reassessment_score": 0.9,
        "future_pass_status": True,
        "learning_time_spent_hours": 15
    }
    feats = build_weakness_features([attempt])
    item = feats[0]

    for key in item.keys():
        assert "t2" not in key
        assert "future" not in key
        assert "learning" not in key
