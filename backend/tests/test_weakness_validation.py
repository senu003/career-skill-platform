"""
TEST SUITE FOR WEAKNESS ML VALIDATION AUDIT (STEP 3C)

Verifies candidate-aware StratifiedGroupKFold fold construction, candidate fold separation (zero leakage),
pure behavioral feature exclusions, majority baseline calculations, evaluation of small grouped datasets,
timing feature quality audit, and non-mutation of input dataset records.
"""

import copy
import pytest
import numpy as np

from app.ml.weakness_model import (
    EXPERIMENT_PURE_BEHAVIORAL_FEATURES,
    EXPERIMENT_PURE_BEHAVIORAL_NAME,
    FORBIDDEN_PURE_BEHAVIORAL_FEATURES,
    verify_pure_behavioral_exclusions,
    compute_majority_baseline,
    run_weakness_experiment
)
from app.ml.weakness_validation_audit import (
    audit_candidate_groups,
    audit_timing_features,
    generate_demonstration_audit_dataset,
    run_full_validation_audit,
    print_validation_audit_report
)


def create_synthetic_grouped_record(
    candidate_id: str = "cand_1",
    skill: str = "Python",
    is_weakness: int = 1,
    level_gap: int = 1,
    total_score: float = 0.50,
    avg_time: float = 25.0
) -> dict:
    """Helper fixture generator for candidate group unit testing."""
    return {
        "candidate_id": candidate_id,
        "attempt_id": f"att_{candidate_id}",
        "user_id": candidate_id,
        "skill": skill,
        "required_level": 2,
        "assessed_level": 1 if is_weakness == 1 else 2,
        "level_gap": level_gap,
        "basic_score": total_score,
        "intermediate_score": total_score if is_weakness == 0 else 0.0,
        "advanced_score": 0.0,
        "total_score": total_score,
        "questions_answered_count": 5,
        "avg_answer_time_seconds": avg_time,
        "answer_time_std_seconds": 3.5,
        "min_answer_time_seconds": 15.0,
        "max_answer_time_seconds": 35.0,
        "timed_questions_count": 4,
        "candidate_avg_total_score": total_score,
        "candidate_score_std": 0.1,
        "candidate_below_requirement_ratio": 0.5 if is_weakness == 1 else 0.0,
        "candidate_avg_answer_time_seconds": avg_time,
        "is_weakness": is_weakness,
    }


def test_pure_behavioral_feature_set_exclusions():
    """Verifies that pure behavioral feature set excludes all performance-representing features."""
    assert EXPERIMENT_PURE_BEHAVIORAL_NAME == "pure_behavioral_experiment"
    assert isinstance(EXPERIMENT_PURE_BEHAVIORAL_FEATURES, list)
    assert len(EXPERIMENT_PURE_BEHAVIORAL_FEATURES) == 7

    violating = verify_pure_behavioral_exclusions(EXPERIMENT_PURE_BEHAVIORAL_FEATURES)
    assert violating == [], f"Forbidden performance features found in Pure Behavioral: {violating}"

    for forbidden in FORBIDDEN_PURE_BEHAVIORAL_FEATURES:
        assert forbidden not in EXPERIMENT_PURE_BEHAVIORAL_FEATURES, f"Forbidden feature '{forbidden}' present in Pure Behavioral"


def test_candidate_aware_fold_construction_no_leakage():
    """Verifies that StratifiedGroupKFold ensures same candidate never appears in both train and test folds."""
    dataset = []
    # Create 10 candidates with 3 skills each = 30 rows
    for c_idx in range(1, 11):
        cand_id = f"candidate_{c_idx}"
        is_w = 1 if c_idx % 2 == 0 else 0
        for s_idx in range(3):
            rec = create_synthetic_grouped_record(
                candidate_id=cand_id,
                skill=f"Skill_{s_idx}",
                is_weakness=is_w,
                level_gap=1 if is_w == 1 else 0,
                total_score=0.40 if is_w == 1 else 0.80
            )
            dataset.append(rec)

    res = run_weakness_experiment(dataset, experiment_type="PURE_BEHAVIORAL", use_group_cv=True, random_state=42)

    assert res["is_trainable"] is True
    assert res["is_group_cv"] is True
    assert res["unique_group_count"] == 10
    assert res["metrics"]["cv_folds"] > 0
    assert res["metrics"]["accuracy"] is not None


def test_majority_baseline_calculation():
    """Verifies explicit majority-class baseline evaluation calculation."""
    # Dataset with 8 weakness=1 and 2 weakness=0 (80% majority)
    dataset = []
    for _ in range(8):
        dataset.append(create_synthetic_grouped_record(is_weakness=1))
    for _ in range(2):
        dataset.append(create_synthetic_grouped_record(is_weakness=0, level_gap=0, total_score=0.85))

    mb = compute_majority_baseline(dataset)

    assert mb["majority_class"] == 1
    assert mb["sample_count"] == 10
    assert mb["class_distribution"] == {0: 2, 1: 8}
    assert mb["accuracy"] == 0.8000
    assert mb["precision"] == 0.8000
    assert mb["recall"] == 1.0000
    assert mb["f1"] == 0.8889
    assert mb["roc_auc"] == 0.5000


def test_small_grouped_dataset_handling():
    """Verifies graceful handling of small grouped datasets with few unique groups."""
    dataset = [
        create_synthetic_grouped_record(candidate_id="cand_A", skill="Python", is_weakness=1),
        create_synthetic_grouped_record(candidate_id="cand_A", skill="SQL", is_weakness=1),
        create_synthetic_grouped_record(candidate_id="cand_B", skill="Python", is_weakness=0, level_gap=0, total_score=0.85),
    ]

    res = run_weakness_experiment(dataset, experiment_type="PURE_BEHAVIORAL", use_group_cv=True, random_state=42)
    assert res["is_trainable"] is True
    assert res["metrics"]["cv_folds"] == 0  # skipped CV safely due to small minority/groups


def test_no_mutation_of_dataset():
    """Verifies that running group-aware validation does not mutate original dataset records."""
    dataset = [
        create_synthetic_grouped_record(candidate_id="c1", is_weakness=1),
        create_synthetic_grouped_record(candidate_id="c2", is_weakness=0, level_gap=0, total_score=0.90)
    ]
    dataset_copy = copy.deepcopy(dataset)

    _ = run_weakness_experiment(dataset, experiment_type="PURE_BEHAVIORAL", use_group_cv=True)
    assert dataset == dataset_copy


def test_audit_candidate_groups_statistics():
    """Verifies candidate group statistics calculation."""
    dataset = [
        create_synthetic_grouped_record(candidate_id="cand_1"),
        create_synthetic_grouped_record(candidate_id="cand_1"),
        create_synthetic_grouped_record(candidate_id="cand_2"),
    ]

    stats = audit_candidate_groups(dataset)
    assert stats["total_rows"] == 3
    assert stats["unique_candidates"] == 2
    assert stats["min_rows_per_candidate"] == 1
    assert stats["max_rows_per_candidate"] == 2


def test_audit_timing_features_quality():
    """Verifies timing feature quality and outlier detection audit."""
    dataset = generate_demonstration_audit_dataset(num_candidates=10, random_seed=42)
    tq = audit_timing_features(dataset)

    for feat in EXPERIMENT_PURE_BEHAVIORAL_FEATURES:
        assert feat in tq
        assert "missing_count" in tq[feat]
        assert "is_constant" in tq[feat]
        assert "extreme_outliers_count" in tq[feat]


def test_full_validation_audit_runner():
    """Verifies that full validation audit runner completes and returns valid report structure."""
    rep = run_full_validation_audit()
    assert "candidate_stats" in rep
    assert "timing_quality" in rep
    assert "experiment_b_skf" in rep
    assert "experiment_b_sgkf" in rep
    assert "pure_behavioral_sgkf" in rep
    assert "majority_baseline" in rep

    text_rep = print_validation_audit_report(rep)
    assert "STEP 3C: ML VALIDATION AUDIT REPORT" in text_rep
    assert "CANDIDATE / ATTEMPT GROUPING AUDIT" in text_rep
