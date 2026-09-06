"""
TEST SUITE FOR WEAKNESS ML TRAINING & EVALUATION MODULE

Verifies feature set definitions, explicit feature exclusions, dataset validation,
insufficient data handling, baseline model training, probability output bounds,
dynamic cross-validation fold selection, metric generation, non-mutation of input data,
and reproducible model fitting.
"""

import copy
import pytest
import numpy as np

from app.ml.weakness_model import (
    EXPERIMENT_A_FEATURES,
    EXPERIMENT_B_FEATURES,
    EXPERIMENT_PURE_BEHAVIORAL_FEATURES,
    EXPERIMENT_A_NAME,
    EXPERIMENT_B_NAME,
    EXPERIMENT_PURE_BEHAVIORAL_NAME,
    FORBIDDEN_BEHAVIORAL_FEATURES,
    FORBIDDEN_PURE_BEHAVIORAL_FEATURES,
    verify_feature_exclusions,
    verify_pure_behavioral_exclusions,
    compute_majority_baseline,
    validate_training_dataset,
    build_baseline_model,
    predict_weakness_probability,
    run_weakness_experiment,
)


def create_synthetic_test_record(
    skill: str = "Python",
    is_weakness: int = 1,
    level_gap: int = 1,
    total_score: float = 0.50,
    avg_time: float = 25.0
) -> dict:
    """Helper fixture generator isolated to unit tests only."""
    return {
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


def test_feature_set_definitions():
    """Verifies feature set names and non-empty feature lists."""
    assert EXPERIMENT_A_NAME == "target_reconstruction_experiment"
    assert EXPERIMENT_B_NAME == "behavioral_experiment"

    assert isinstance(EXPERIMENT_A_FEATURES, list) and len(EXPERIMENT_A_FEATURES) > 0
    assert isinstance(EXPERIMENT_B_FEATURES, list) and len(EXPERIMENT_B_FEATURES) > 0


def test_correct_feature_exclusion_in_experiment_b():
    """Verifies that none of the forbidden target-defining features exist in Experiment B."""
    violating_features = verify_feature_exclusions(EXPERIMENT_B_FEATURES)
    assert violating_features == [], f"Forbidden features found in Experiment B: {violating_features}"

    for forbidden in FORBIDDEN_BEHAVIORAL_FEATURES:
        assert forbidden not in EXPERIMENT_B_FEATURES, f"Forbidden feature '{forbidden}' present in Exp B"


def test_two_class_validation():
    """Verifies that datasets with only 1 class are rejected from training."""
    # Dataset containing only class 1
    single_class_1 = [create_synthetic_test_record(is_weakness=1) for _ in range(5)]
    is_valid, reason, counts = validate_training_dataset(single_class_1)
    assert is_valid is False
    assert "at least 2 distinct classes" in reason.lower()
    assert counts == {0: 0, 1: 5}

    with pytest.raises(ValueError, match=r"(?i)at least 2 distinct classes"):
        run_weakness_experiment(single_class_1, experiment_type="B")

    # Dataset containing only class 0
    single_class_0 = [create_synthetic_test_record(is_weakness=0, level_gap=0, total_score=0.85) for _ in range(5)]
    is_valid_0, reason_0, counts_0 = validate_training_dataset(single_class_0)
    assert is_valid_0 is False
    assert counts_0 == {0: 5, 1: 0}


def test_insufficient_data_handling():
    """Verifies graceful rejection of empty or invalid datasets."""
    is_valid, reason, counts = validate_training_dataset([])
    assert is_valid is False
    assert "empty" in reason.lower()

    with pytest.raises(ValueError, match="validation failed"):
        run_weakness_experiment([], experiment_type="B")


def test_small_valid_dataset_training():
    """Verifies model training on a small balanced dataset (10 records)."""
    dataset = []
    for i in range(5):
        dataset.append(create_synthetic_test_record(skill=f"Skill_{i}", is_weakness=1, level_gap=1, total_score=0.40))
        dataset.append(create_synthetic_test_record(skill=f"Skill_{i}", is_weakness=0, level_gap=0, total_score=0.85))

    res_a = run_weakness_experiment(dataset, experiment_type="A", random_state=42)
    assert res_a["is_trainable"] is True
    assert res_a["experiment_name"] == EXPERIMENT_A_NAME
    assert res_a["sample_count"] == 10
    assert res_a["model"] is not None

    res_b = run_weakness_experiment(dataset, experiment_type="B", random_state=42)
    assert res_b["is_trainable"] is True
    assert res_b["experiment_name"] == EXPERIMENT_B_NAME
    assert res_b["sample_count"] == 10


def test_probability_output_between_0_and_1():
    """Verifies that predicted weakness probabilities are strictly bounded between 0.0 and 1.0."""
    dataset = []
    for i in range(6):
        dataset.append(create_synthetic_test_record(is_weakness=1, total_score=0.30, avg_time=10.0 + i))
        dataset.append(create_synthetic_test_record(is_weakness=0, level_gap=0, total_score=0.90, avg_time=40.0 + i))

    res = run_weakness_experiment(dataset, experiment_type="B", random_state=42)
    model = res["model"]
    feature_names = res["feature_names"]

    # Single sample prediction
    sample_feat = dataset[0]
    prob_single = predict_weakness_probability(model, sample_feat, feature_names=feature_names)
    assert isinstance(prob_single, float)
    assert 0.0 <= prob_single <= 1.0

    # Multiple sample prediction
    probs_multi = predict_weakness_probability(model, dataset, feature_names=feature_names)
    assert isinstance(probs_multi, list)
    assert len(probs_multi) == len(dataset)
    for p in probs_multi:
        assert isinstance(p, float)
        assert 0.0 <= p <= 1.0


def test_cross_validation_fold_selection():
    """Verifies dynamic fold selection: n_splits = min(5, minority_class_count)."""
    # Dataset with minority count = 3 (3 class 0, 7 class 1)
    dataset = []
    for i in range(7):
        dataset.append(create_synthetic_test_record(is_weakness=1))
    for i in range(3):
        dataset.append(create_synthetic_test_record(is_weakness=0, level_gap=0, total_score=0.80))

    res = run_weakness_experiment(dataset, experiment_type="B", random_state=42)
    assert res["metrics"]["cv_folds"] == 3

    # Dataset with minority count = 1 (1 class 0, 5 class 1) -> minority < 2 -> skip CV safely
    dataset_skewed = [create_synthetic_test_record(is_weakness=1) for _ in range(5)]
    dataset_skewed.append(create_synthetic_test_record(is_weakness=0, level_gap=0, total_score=0.80))

    res_skewed = run_weakness_experiment(dataset_skewed, experiment_type="B", random_state=42)
    assert res_skewed["metrics"]["cv_folds"] == 0
    assert any("skipped" in w.lower() for w in res_skewed["warnings"])


def test_metrics_generation():
    """Verifies metrics structure and safe numerical bounds."""
    dataset = []
    for i in range(5):
        dataset.append(create_synthetic_test_record(is_weakness=1, total_score=0.40))
        dataset.append(create_synthetic_test_record(is_weakness=0, level_gap=0, total_score=0.85))

    res = run_weakness_experiment(dataset, experiment_type="B", random_state=42)
    m = res["metrics"]

    assert "accuracy" in m
    assert "precision" in m
    assert "recall" in m
    assert "f1" in m
    assert "roc_auc" in m
    assert "pr_auc" in m

    assert m["accuracy"] is not None and 0.0 <= m["accuracy"] <= 1.0


def test_no_mutation_of_dataset():
    """Verifies that model training does not mutate original dataset records."""
    dataset = [
        create_synthetic_test_record(is_weakness=1),
        create_synthetic_test_record(is_weakness=0, level_gap=0, total_score=0.80)
    ]
    dataset_copy = copy.deepcopy(dataset)

    _ = run_weakness_experiment(dataset, experiment_type="B", random_state=42)

    assert dataset == dataset_copy


def test_deterministic_reproducible_behavior():
    """Verifies reproducible metrics when random_state is fixed."""
    dataset = []
    for i in range(10):
        dataset.append(create_synthetic_test_record(is_weakness=1, total_score=0.30 + i * 0.02))
        dataset.append(create_synthetic_test_record(is_weakness=0, level_gap=0, total_score=0.70 + i * 0.02))

    res1 = run_weakness_experiment(dataset, experiment_type="B", random_state=42)
    res2 = run_weakness_experiment(dataset, experiment_type="B", random_state=42)

    assert res1["metrics"] == res2["metrics"]


def test_pure_behavioral_experiment_execution():
    """Verifies execution of Pure Behavioral experiment with strict exclusions."""
    dataset = []
    for i in range(5):
        dataset.append(create_synthetic_test_record(skill=f"Skill_{i}", is_weakness=1, avg_time=15.0 + i))
        dataset.append(create_synthetic_test_record(skill=f"Skill_{i}", is_weakness=0, level_gap=0, total_score=0.85, avg_time=30.0 + i))

    res = run_weakness_experiment(dataset, experiment_type="PURE_BEHAVIORAL", use_group_cv=False, random_state=42)
    assert res["is_trainable"] is True
    assert res["experiment_name"] == EXPERIMENT_PURE_BEHAVIORAL_NAME
    assert res["feature_names"] == EXPERIMENT_PURE_BEHAVIORAL_FEATURES


def test_majority_baseline_computation():
    """Verifies majority baseline metric calculation."""
    dataset = [create_synthetic_test_record(is_weakness=1) for _ in range(4)]
    dataset.append(create_synthetic_test_record(is_weakness=0, level_gap=0, total_score=0.90))

    mb = compute_majority_baseline(dataset)
    assert mb["majority_class"] == 1
    assert mb["sample_count"] == 5
    assert mb["accuracy"] == 0.8000

