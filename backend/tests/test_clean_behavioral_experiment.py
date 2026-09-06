"""
TESTS FOR CLEAN BEHAVIORAL EXPERIMENT MODULE (STEP 4B)
"""

import sys
import os
import copy
import pytest
import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ml.clean_behavioral_experiment import (
    CLEAN_BEHAVIORAL_EXPERIMENT_FEATURES,
    EXCLUDED_FEATURES_RATIONALE,
    filter_clean_behavioral_dataset,
    compute_clean_descriptive_stats,
    run_clean_behavioral_experiment,
    format_clean_experiment_report
)


@pytest.fixture
def mock_raw_dataset():
    """
    Creates a mock raw dataset containing valid timing rows as well as unassessed rows.
    """
    return [
        # Candidate 1: valid assessed rows
        {
            "candidate_id": "cand_1",
            "attempt_id": "att_1",
            "skill": "Python",
            "questions_answered_count": 10,
            "timed_questions_count": 9,
            "avg_answer_time_seconds": 25.0,
            "answer_time_std_seconds": 3.5,
            "min_answer_time_seconds": 15.0,
            "max_answer_time_seconds": 35.0,
            "candidate_avg_answer_time_seconds": 25.0,
            "total_score": 0.8,
            "is_weakness": 0
        },
        {
            "candidate_id": "cand_1",
            "attempt_id": "att_1",
            "skill": "SQL",
            "questions_answered_count": 8,
            "timed_questions_count": 7,
            "avg_answer_time_seconds": 18.0,
            "answer_time_std_seconds": 2.1,
            "min_answer_time_seconds": 12.0,
            "max_answer_time_seconds": 24.0,
            "candidate_avg_answer_time_seconds": 25.0,
            "total_score": 0.4,
            "is_weakness": 1
        },
        # Candidate 2: unassessed skill rows (questions_answered_count = 0)
        {
            "candidate_id": "cand_2",
            "attempt_id": "att_2",
            "skill": "Docker",
            "questions_answered_count": 0,
            "timed_questions_count": 0,
            "avg_answer_time_seconds": 0.0,
            "answer_time_std_seconds": 0.0,
            "min_answer_time_seconds": 0.0,
            "max_answer_time_seconds": 0.0,
            "candidate_avg_answer_time_seconds": 20.0,
            "total_score": 0.0,
            "is_weakness": 1
        },
        # Candidate 3: valid assessed rows
        {
            "candidate_id": "cand_3",
            "attempt_id": "att_3",
            "skill": "FastAPI",
            "questions_answered_count": 5,
            "timed_questions_count": 4,
            "avg_answer_time_seconds": 30.0,
            "answer_time_std_seconds": 4.0,
            "min_answer_time_seconds": 20.0,
            "max_answer_time_seconds": 40.0,
            "candidate_avg_answer_time_seconds": 30.0,
            "total_score": 0.9,
            "is_weakness": 0
        },
        {
            "candidate_id": "cand_3",
            "attempt_id": "att_3",
            "skill": "AWS",
            "questions_answered_count": 6,
            "timed_questions_count": 5,
            "avg_answer_time_seconds": 12.0,
            "answer_time_std_seconds": 1.5,
            "min_answer_time_seconds": 8.0,
            "max_answer_time_seconds": 16.0,
            "candidate_avg_answer_time_seconds": 30.0,
            "total_score": 0.35,
            "is_weakness": 1
        }
    ]


def test_correct_feature_inclusion_and_exclusion():
    """
    Verifies that CLEAN_BEHAVIORAL_EXPERIMENT_FEATURES contains only genuine timing features
    and excludes volume shortcuts and performance leakage features.
    """
    allowed_features = [
        "avg_answer_time_seconds",
        "answer_time_std_seconds",
        "min_answer_time_seconds",
        "max_answer_time_seconds"
    ]
    assert CLEAN_BEHAVIORAL_EXPERIMENT_FEATURES == allowed_features

    disallowed_features = [
        "questions_answered_count",
        "timed_questions_count",
        "candidate_avg_answer_time_seconds",
        "level_gap",
        "total_score",
        "candidate_below_requirement_ratio",
        "required_level",
        "assessed_level",
        "basic_score",
        "intermediate_score",
        "advanced_score",
        "candidate_avg_total_score",
        "candidate_score_std"
    ]

    for df in disallowed_features:
        assert df not in CLEAN_BEHAVIORAL_EXPERIMENT_FEATURES
        assert df in EXCLUDED_FEATURES_RATIONALE


def test_unassessed_rows_exclusion_and_reporting(mock_raw_dataset):
    """
    Verifies that unassessed rows (questions_answered_count == 0) are excluded
    and that exclusion counts are accurately reported.
    """
    clean_ds, metadata, active_feats = filter_clean_behavioral_dataset(mock_raw_dataset)

    assert metadata["original_row_count"] == 5
    assert metadata["excluded_rows_count"] == 1
    assert metadata["final_clean_row_count"] == 4
    assert len(clean_ds) == 4

    # Verify that the unassessed skill 'Docker' was excluded
    skills_in_clean = [r["skill"] for r in clean_ds]
    assert "Docker" not in skills_in_clean
    assert set(skills_in_clean) == {"Python", "SQL", "FastAPI", "AWS"}


def test_valid_timing_rows_retained(mock_raw_dataset):
    """
    Verifies that rows with valid timing evidence are fully retained.
    """
    clean_ds, metadata, _ = filter_clean_behavioral_dataset(mock_raw_dataset)
    for row in clean_ds:
        assert row["questions_answered_count"] > 0
        assert row["timed_questions_count"] > 0
        assert row["avg_answer_time_seconds"] > 0.0


def test_constant_feature_handling():
    """
    Verifies that zero-variance (constant) features in the clean dataset are detected
    and excluded from active_features without mutating dataset records.
    """
    ds_with_constant = [
        {
            "candidate_id": "c1",
            "questions_answered_count": 5,
            "timed_questions_count": 4,
            "avg_answer_time_seconds": 20.0,
            "answer_time_std_seconds": 0.0,  # Constant zero across all rows
            "min_answer_time_seconds": 15.0,
            "max_answer_time_seconds": 25.0,
            "is_weakness": 0
        },
        {
            "candidate_id": "c2",
            "questions_answered_count": 6,
            "timed_questions_count": 5,
            "avg_answer_time_seconds": 30.0,
            "answer_time_std_seconds": 0.0,  # Constant zero across all rows
            "min_answer_time_seconds": 20.0,
            "max_answer_time_seconds": 40.0,
            "is_weakness": 1
        }
    ]

    clean_ds, metadata, active_feats = filter_clean_behavioral_dataset(ds_with_constant)
    assert "answer_time_std_seconds" in metadata["constant_features_excluded"]
    assert "answer_time_std_seconds" not in active_feats
    assert "avg_answer_time_seconds" in active_feats


def test_candidate_aware_fold_construction(mock_raw_dataset):
    """
    Verifies StratifiedGroupKFold ensures no candidate appears in both train and validation folds.
    """
    clean_ds, _, active_feats = filter_clean_behavioral_dataset(mock_raw_dataset)
    X_mat = np.array([[float(r[f]) for f in active_feats] for r in clean_ds])
    y_vec = np.array([int(r["is_weakness"]) for r in clean_ds])
    groups = np.array([r["candidate_id"] for r in clean_ds])

    sgkf = StratifiedGroupKFold(n_splits=2)
    for train_idx, val_idx in sgkf.split(X_mat, y_vec, groups):
        train_cands = set(groups[train_idx])
        val_cands = set(groups[val_idx])

        # Intersection must be completely empty (zero candidate leakage)
        assert train_cands.intersection(val_cands) == set()


def test_small_data_and_single_class_handling():
    """
    Verifies that small datasets or single-class clean datasets are handled gracefully without crashing.
    """
    single_class_ds = [
        {
            "candidate_id": "c1",
            "questions_answered_count": 5,
            "timed_questions_count": 4,
            "avg_answer_time_seconds": 20.0,
            "answer_time_std_seconds": 2.0,
            "min_answer_time_seconds": 15.0,
            "max_answer_time_seconds": 25.0,
            "is_weakness": 0
        },
        {
            "candidate_id": "c2",
            "questions_answered_count": 6,
            "timed_questions_count": 5,
            "avg_answer_time_seconds": 22.0,
            "answer_time_std_seconds": 3.0,
            "min_answer_time_seconds": 16.0,
            "max_answer_time_seconds": 28.0,
            "is_weakness": 0
        }
    ]

    results = run_clean_behavioral_experiment(single_class_ds, random_state=42)
    assert results is not None
    assert "metadata" in results
    assert "clean_behavioral_metrics" in results


def test_probability_output_validity():
    """
    Verifies that trained clean behavioral model produces probabilities in valid range [0.0, 1.0].
    """
    results = run_clean_behavioral_experiment(random_state=42)
    model = results.get("trained_model")
    active_feats = results.get("active_features", [])

    if model is not None and active_feats:
        dummy_X = np.random.uniform(10.0, 50.0, size=(10, len(active_feats)))
        probs = model.predict_proba(dummy_X)[:, 1]

        assert len(probs) == 10
        assert np.all(probs >= 0.0)
        assert np.all(probs <= 1.0)


def test_no_input_dataset_mutation(mock_raw_dataset):
    """
    Verifies that running filter and experiment functions never mutates the original dataset.
    """
    original_copy = copy.deepcopy(mock_raw_dataset)

    _ = filter_clean_behavioral_dataset(mock_raw_dataset)
    _ = compute_clean_descriptive_stats(mock_raw_dataset, CLEAN_BEHAVIORAL_EXPERIMENT_FEATURES)
    _ = run_clean_behavioral_experiment(mock_raw_dataset)

    assert mock_raw_dataset == original_copy


def test_descriptive_stats_computation(mock_raw_dataset):
    """
    Verifies accuracy of clean descriptive statistics computation.
    """
    clean_ds, _, active_feats = filter_clean_behavioral_dataset(mock_raw_dataset)
    stats = compute_clean_descriptive_stats(clean_ds, active_feats)

    assert isinstance(stats, dict)
    for f in active_feats:
        assert "is_weakness_0" in stats[f]
        assert "is_weakness_1" in stats[f]

        g0 = stats[f]["is_weakness_0"]
        g1 = stats[f]["is_weakness_1"]

        assert g0["count"] == 2
        assert g1["count"] == 2
        assert g0["mean"] > 0
        assert g1["mean"] > 0
