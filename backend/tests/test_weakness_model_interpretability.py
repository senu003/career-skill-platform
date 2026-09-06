"""
TESTS FOR WEAKNESS ML MODEL INTERPRETABILITY ANALYSIS MODULE (STEP 4A)
"""

import copy
import sys
import os
import pytest
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.ml.weakness_model_interpretability import (
    extract_model_coefficients,
    rank_feature_importance,
    perform_feature_sanity_checks,
    compute_univariate_stats,
    compute_effect_sizes,
    investigate_roc_auc_drivers,
    run_interpretability_analysis
)
from app.ml.weakness_model import EXPERIMENT_PURE_BEHAVIORAL_FEATURES, build_baseline_model


@pytest.fixture
def mock_trained_model():
    """
    Creates a small isolated, trained LogisticRegression pipeline for testing coefficient extraction.
    """
    feature_names = EXPERIMENT_PURE_BEHAVIORAL_FEATURES
    np.random.seed(42)
    X = np.random.randn(50, len(feature_names))
    # Synthetic target with strong correlation to first two features
    y = ((X[:, 0] * 1.5 - X[:, 1] * 2.0 + X[:, 2] * 0.5) > 0).astype(int)

    pipeline = build_baseline_model(random_state=42)
    pipeline.fit(X, y)
    return pipeline, feature_names


@pytest.fixture
def mock_dataset():
    """
    Creates a small isolated dataset fixture (no real data manufactured).
    """
    return [
        {
            "questions_answered_count": 10,
            "avg_answer_time_seconds": 25.0,
            "answer_time_std_seconds": 3.0,
            "min_answer_time_seconds": 15.0,
            "max_answer_time_seconds": 35.0,
            "timed_questions_count": 9,
            "candidate_avg_answer_time_seconds": 25.0,
            "is_weakness": 0
        },
        {
            "questions_answered_count": 12,
            "avg_answer_time_seconds": 28.0,
            "answer_time_std_seconds": 4.0,
            "min_answer_time_seconds": 18.0,
            "max_answer_time_seconds": 40.0,
            "timed_questions_count": 11,
            "candidate_avg_answer_time_seconds": 25.0,
            "is_weakness": 0
        },
        {
            "questions_answered_count": 0,
            "avg_answer_time_seconds": 0.0,
            "answer_time_std_seconds": 0.0,
            "min_answer_time_seconds": 0.0,
            "max_answer_time_seconds": 0.0,
            "timed_questions_count": 0,
            "candidate_avg_answer_time_seconds": 25.0,
            "is_weakness": 1
        },
        {
            "questions_answered_count": 1,
            "avg_answer_time_seconds": 12.0,
            "answer_time_std_seconds": 0.0,
            "min_answer_time_seconds": 12.0,
            "max_answer_time_seconds": 12.0,
            "timed_questions_count": 0,
            "candidate_avg_answer_time_seconds": 25.0,
            "is_weakness": 1
        }
    ]


def test_coefficient_extraction(mock_trained_model):
    pipeline, feature_names = mock_trained_model
    coef_records = extract_model_coefficients(pipeline, feature_names)

    assert isinstance(coef_records, list)
    assert len(coef_records) == len(feature_names)

    extracted_names = [r["feature"] for r in coef_records]
    assert extracted_names == feature_names

    for record in coef_records:
        assert "coefficient" in record
        assert "absolute_coefficient" in record
        assert "direction" in record
        assert "normalized_relative_importance" in record
        assert "description" in record
        assert record["absolute_coefficient"] == pytest.approx(abs(record["coefficient"]), abs=1e-4)
        assert record["direction"] in ("positive", "negative", "zero")
        assert "associated with" in record["description"]
        assert "causes" not in record["description"].lower()

    # Verify normalized relative importance sums to 1.0
    rel_sum = sum(r["normalized_relative_importance"] for r in coef_records)
    assert rel_sum == pytest.approx(1.0, abs=1e-3)


def test_feature_names_matching_validation(mock_trained_model):
    pipeline, feature_names = mock_trained_model

    # Passing mismatched length feature_names should raise ValueError
    with pytest.raises(ValueError, match="Length mismatch"):
        extract_model_coefficients(pipeline, feature_names[:3])


def test_empty_invalid_model_handling():
    with pytest.raises(ValueError, match="Cannot extract coefficients"):
        extract_model_coefficients(None, ["feat1"])

    class EmptyObj:
        pass

    with pytest.raises(ValueError, match="does not contain fitted coefficients"):
        extract_model_coefficients(EmptyObj(), ["feat1"])


def test_coefficient_ranking(mock_trained_model):
    pipeline, feature_names = mock_trained_model
    coef_records = extract_model_coefficients(pipeline, feature_names)
    ranking = rank_feature_importance(coef_records)

    assert "ranked_features" in ranking
    assert "top_3_features" in ranking
    assert "top_5_features" in ranking
    assert "weakest_features" in ranking

    ranked = ranking["ranked_features"]
    assert len(ranked) == len(feature_names)

    # Check sorting order: absolute_coefficient must be non-increasing
    abs_vals = [r["absolute_coefficient"] for r in ranked]
    assert abs_vals == sorted(abs_vals, reverse=True)

    assert len(ranking["top_3_features"]) == 3
    assert len(ranking["top_5_features"]) == 5
    assert len(ranking["weakest_features"]) == 3

    assert ranking["top_3_features"] == [r["feature"] for r in ranked[:3]]


def test_positive_negative_direction_classification():
    records = [
        {"feature": "f1", "coefficient": 1.5, "absolute_coefficient": 1.5, "direction": "positive", "normalized_relative_importance": 0.5, "description": "higher associated with higher"},
        {"feature": "f2", "coefficient": -1.0, "absolute_coefficient": 1.0, "direction": "negative", "normalized_relative_importance": 0.33, "description": "higher associated with lower"},
        {"feature": "f3", "coefficient": 0.5, "absolute_coefficient": 0.5, "direction": "positive", "normalized_relative_importance": 0.17, "description": "higher associated with higher"}
    ]

    ranking = rank_feature_importance(records)
    assert ranking["positive_direction_features"] == ["f1", "f3"]
    assert ranking["negative_direction_features"] == ["f2"]


def test_univariate_stats_generation(mock_dataset):
    feature_names = EXPERIMENT_PURE_BEHAVIORAL_FEATURES
    stats = compute_univariate_stats(mock_dataset, feature_names)

    assert isinstance(stats, dict)
    assert len(stats) == len(feature_names)

    for f in feature_names:
        assert "is_weakness_0" in stats[f]
        assert "is_weakness_1" in stats[f]

        g0 = stats[f]["is_weakness_0"]
        g1 = stats[f]["is_weakness_1"]

        assert g0["count"] == 2
        assert g1["count"] == 2

        for metric in ["count", "mean", "median", "std", "min", "max"]:
            assert metric in g0
            assert metric in g1

    # Verify questions_answered_count numbers specifically
    q_stats = stats["questions_answered_count"]
    assert q_stats["is_weakness_0"]["mean"] == 11.0
    assert q_stats["is_weakness_1"]["mean"] == 0.5


def test_effect_sizes_computation(mock_dataset):
    feature_names = EXPERIMENT_PURE_BEHAVIORAL_FEATURES
    eff = compute_effect_sizes(mock_dataset, feature_names)

    assert isinstance(eff, dict)
    for f in feature_names:
        assert "cohens_d" in eff[f]
        assert "effect_magnitude" in eff[f]
        assert isinstance(eff[f]["cohens_d"], float)

    # questions_answered_count should have negative Cohen's d (lower in weakness group 1)
    assert eff["questions_answered_count"]["cohens_d"] < 0


def test_feature_sanity_checks(mock_dataset):
    feature_names = EXPERIMENT_PURE_BEHAVIORAL_FEATURES
    sanity = perform_feature_sanity_checks(mock_dataset, feature_names)

    assert isinstance(sanity, dict)
    assert len(sanity) == len(feature_names)

    for f in feature_names:
        s = sanity[f]
        assert "missing_count" in s
        assert "zero_variance" in s
        assert "min" in s
        assert "max" in s
        assert "outliers_count" in s
        assert "identical_groups" in s

    # candidate_avg_answer_time_seconds has identical values for group 0 and group 1 in mock dataset (25.0 vs 25.0)
    assert sanity["candidate_avg_answer_time_seconds"]["identical_groups"] is True


def test_no_mutation_of_input_dataset(mock_dataset):
    original_dataset = copy.deepcopy(mock_dataset)

    _ = compute_univariate_stats(mock_dataset, EXPERIMENT_PURE_BEHAVIORAL_FEATURES)
    _ = compute_effect_sizes(mock_dataset, EXPERIMENT_PURE_BEHAVIORAL_FEATURES)
    _ = perform_feature_sanity_checks(mock_dataset, EXPERIMENT_PURE_BEHAVIORAL_FEATURES)

    assert mock_dataset == original_dataset


def test_roc_auc_driver_investigation(mock_trained_model):
    pipeline, feature_names = mock_trained_model
    coef_records = extract_model_coefficients(pipeline, feature_names)
    ranking = rank_feature_importance(coef_records)

    driver_info = investigate_roc_auc_drivers(ranking, {}, {})
    assert "primary_driver_category" in driver_info
    assert "explanation" in driver_info
    assert "top_2_normalized_importance_sum" in driver_info


def test_run_interpretability_analysis_end_to_end():
    report_dict = run_interpretability_analysis(experiment_type="PURE_BEHAVIORAL")

    assert "sample_count" in report_dict
    assert "coefficients" in report_dict
    assert "ranking" in report_dict
    assert "sanity_checks" in report_dict
    assert "univariate_stats" in report_dict
    assert "effect_sizes" in report_dict
    assert "roc_auc_driver_analysis" in report_dict
    assert "report_text" in report_dict

    report_text = report_dict["report_text"]
    assert "STEP 4A: WEAKNESS ML MODEL INTERPRETABILITY REPORT" in report_text
    assert "RANKED STANDARDIZED FEATURE COEFFICIENTS" in report_text
    assert "ROC-AUC DRIVER ANALYSIS" in report_text
