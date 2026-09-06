"""
TESTS FOR ML TARGET & ARCHITECTURE REDESIGN INVESTIGATION MODULE (STEP 5)
"""

import sys
import os
import copy
import pytest
from datetime import datetime, timedelta

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ml.target_redesign_analysis import (
    analyze_assessment_history,
    analyze_repeated_skills,
    check_temporal_ordering,
    evaluate_improvement_targets,
    audit_data_quality_and_leakage,
    perform_data_sufficiency_analysis,
    make_decision_recommendation,
    run_target_redesign_investigation,
    level_to_numeric
)


@pytest.fixture
def mock_attempts_dataset():
    """
    Isolated mock attempt dataset with repeated candidates and repeated skills across timestamps.
    """
    now = datetime(2026, 8, 30, 12, 0, 0)
    t1_time = now + timedelta(days=7)
    t2_time = now + timedelta(days=14)

    return [
        # Candidate 101 - Skill: Python (t0: score=0.40, t1: score=0.80 -> Improved)
        {
            "attempt_id": 1,
            "user_id": 101,
            "candidate_id": "101",
            "skill": "Python",
            "required_level": "intermediate",
            "assessed_level": "basic",
            "total_score": 0.40,
            "started_at": now,
            "completed_at": now,
            "is_weakness": 1
        },
        {
            "attempt_id": 2,
            "user_id": 101,
            "candidate_id": "101",
            "skill": "Python",
            "required_level": "intermediate",
            "assessed_level": "intermediate",
            "total_score": 0.80,
            "started_at": t1_time,
            "completed_at": t1_time,
            "is_weakness": 0
        },
        # Candidate 101 - Skill: SQL (t0: score=0.30, t1: score=0.35 -> Persistent Weakness)
        {
            "attempt_id": 3,
            "user_id": 101,
            "candidate_id": "101",
            "skill": "SQL",
            "required_level": "advanced",
            "assessed_level": "basic",
            "total_score": 0.30,
            "started_at": now,
            "completed_at": now,
            "is_weakness": 1
        },
        {
            "attempt_id": 4,
            "user_id": 101,
            "candidate_id": "101",
            "skill": "SQL",
            "required_level": "advanced",
            "assessed_level": "basic",
            "total_score": 0.35,
            "started_at": t1_time,
            "completed_at": t1_time,
            "is_weakness": 1
        },
        # Candidate 102 - 1 attempt only (FastAPI)
        {
            "attempt_id": 5,
            "user_id": 102,
            "candidate_id": "102",
            "skill": "FastAPI",
            "required_level": "intermediate",
            "assessed_level": "intermediate",
            "total_score": 0.75,
            "started_at": now,
            "completed_at": now,
            "is_weakness": 0
        }
    ]


def test_level_to_numeric():
    assert level_to_numeric("basic") == 1
    assert level_to_numeric("intermediate") == 2
    assert level_to_numeric("advanced") == 3
    assert level_to_numeric("none") == 0
    assert level_to_numeric(None) == 0


def test_repeated_candidate_detection(mock_attempts_dataset):
    stats = analyze_assessment_history(mock_attempts_dataset)
    assert stats["total_attempts"] == 5
    assert stats["unique_candidates"] == 2
    assert stats["candidates_1_attempt"] == 1
    assert stats["candidates_2_attempts"] == 0
    assert stats["candidates_3plus_attempts"] == 1  # Candidate 101 has 4 attempts
    assert len(stats["time_spans_days"]) == 1


def test_repeated_skill_matching(mock_attempts_dataset):
    pairs = analyze_repeated_skills(mock_attempts_dataset)
    assert len(pairs) == 2  # Python pair and SQL pair for Candidate 101

    python_pair = next(p for p in pairs if p["skill"] == "Python")
    assert python_pair["candidate_id"] == "101"
    assert python_pair["t0_score"] == 0.40
    assert python_pair["t1_score"] == 0.80
    assert python_pair["score_change"] == 0.40
    assert python_pair["level_change"] == 1  # basic (1) -> intermediate (2)

    sql_pair = next(p for p in pairs if p["skill"] == "SQL")
    assert sql_pair["t0_is_weakness"] == 1
    assert sql_pair["t1_is_weakness"] == 1


def test_chronological_ordering_and_invalid_timestamps(mock_attempts_dataset):
    # Add a record with missing timestamp and reversed ordering
    dataset_with_errors = copy.deepcopy(mock_attempts_dataset)
    dataset_with_errors.append({
        "attempt_id": 6,
        "user_id": 103,
        "candidate_id": "103",
        "skill": "Docker",
        "required_level": "basic",
        "assessed_level": "basic",
        "total_score": 0.5,
        "started_at": None,
        "completed_at": None,
        "is_weakness": 1
    })

    pairs = analyze_repeated_skills(dataset_with_errors)
    ordering_stats = check_temporal_ordering(dataset_with_errors, pairs)

    assert ordering_stats["missing_timestamps_count"] == 1
    assert ordering_stats["duplicate_timestamps_count"] == 0
    assert ordering_stats["reversed_ordering_count"] == 0


def test_score_and_level_change_calculations(mock_attempts_dataset):
    pairs = analyze_repeated_skills(mock_attempts_dataset)
    for p in pairs:
        assert p["score_change"] == pytest.approx(p["t1_score"] - p["t0_score"], abs=1e-4)
        assert p["level_change"] == (p["t1_level_num"] - p["t0_level_num"])


def test_improvement_target_construction(mock_attempts_dataset):
    pairs = analyze_repeated_skills(mock_attempts_dataset)
    target_stats = evaluate_improvement_targets(pairs)

    assert target_stats["total_usable_pairs"] == 2
    # Python improved (+0.40), SQL improved (+0.05)
    assert target_stats["improved_any_score"]["positive"] == 2
    # Python (+0.40 >= 0.10) is positive, SQL (+0.05 < 0.10) is negative
    assert target_stats["improved_score_threshold_0_10"]["positive"] == 1
    assert target_stats["improved_score_threshold_0_10"]["negative"] == 1


def test_persistence_target_construction(mock_attempts_dataset):
    pairs = analyze_repeated_skills(mock_attempts_dataset)
    target_stats = evaluate_improvement_targets(pairs)

    # SQL pair is weakness at both t0 and t1 (persistent weakness = 1)
    assert target_stats["persistent_weakness"]["positive"] == 1
    assert target_stats["persistent_weakness"]["negative"] == 1


def test_candidate_grouping_and_leakage_checks(mock_attempts_dataset):
    pairs = analyze_repeated_skills(mock_attempts_dataset)
    quality = audit_data_quality_and_leakage(mock_attempts_dataset, pairs)

    assert "temporal_leakage_risk" in quality
    assert "candidate_identity_leakage_risk" in quality
    assert "HIGH RISK" in quality["temporal_leakage_risk"]


def test_insufficient_data_handling():
    empty_dataset = []
    stats = analyze_assessment_history(empty_dataset)
    pairs = analyze_repeated_skills(empty_dataset)
    target_stats = evaluate_improvement_targets(pairs)
    task_evals = perform_data_sufficiency_analysis(stats, target_stats)

    assert stats["total_attempts"] == 0
    assert pairs == []
    assert target_stats["total_usable_pairs"] == 0
    assert task_evals["Task_B"]["status"] == "Insufficient"
    assert make_decision_recommendation(task_evals) == "INSUFFICIENT_DATA_FOR_SUPERVISED_ML"


def test_input_immutability(mock_attempts_dataset):
    original_dataset = copy.deepcopy(mock_attempts_dataset)

    _ = analyze_assessment_history(mock_attempts_dataset)
    pairs = analyze_repeated_skills(mock_attempts_dataset)
    _ = check_temporal_ordering(mock_attempts_dataset, pairs)
    _ = evaluate_improvement_targets(pairs)
    _ = audit_data_quality_and_leakage(mock_attempts_dataset, pairs)

    assert mock_attempts_dataset == original_dataset


def test_run_target_redesign_investigation_end_to_end(mock_attempts_dataset):
    results = run_target_redesign_investigation(mock_attempts_dataset)

    assert "history_stats" in results
    assert "repeated_pairs" in results
    assert "temporal_stats" in results
    assert "target_stats" in results
    assert "quality_stats" in results
    assert "task_evaluations" in results
    assert "recommendation" in results
    assert "report_text" in results

    report_text = results["report_text"]
    assert "STEP 5: ML TARGET & ARCHITECTURE REDESIGN INVESTIGATION" in report_text
    assert "RECOMMENDATION:" in report_text
