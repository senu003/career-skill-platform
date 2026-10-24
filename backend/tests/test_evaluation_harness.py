"""
TEST SUITE FOR OFFLINE ML EVALUATION HARNESS (PHASE 3)

Verifies:
1. Metric calculations with known predictions and ground truth.
2. Schema validation error handling for missing/null features and unsupported labels.
3. Missing artifact error handling without retraining.
4. Deterministic seeds and benchmark reproducibility (identical SHA-256).
5. Offline evaluation execution on Model 1 and Model 2 production artifacts.
6. Baseline comparisons (Dummy Classifier and Rule-Based).
7. Challenger disagreement analysis for Model 2.
8. Metadata audit record generation and schema conformance.
"""

import os
import json
import pytest
import numpy as np
import pandas as pd
from pathlib import Path

from app.ml.evaluation_harness import (
    compute_evaluation_metrics,
    validate_benchmark_dataset,
    validate_model_artifact,
    evaluate_dummy_baseline,
    evaluate_model,
    create_model_metadata_record,
    get_or_create_model1_benchmark,
    get_or_create_model2_benchmark,
    MODEL1_FEATURES,
    MODEL1_CLASSES,
    MODEL2_FEATURES,
    MODEL2_CLASSES,
    BASE_DIR,
    MODELS_DIR,
)


def test_metric_calculations_known_predictions():
    """Verifies precision, recall, F1, accuracy, and confusion matrix on known values."""
    y_true = ["A", "A", "B", "B", "C", "C"]
    y_pred = ["A", "B", "B", "B", "C", "A"]
    classes = ["A", "B", "C"]

    # Class A: TP=1, FP=1, FN=1 -> Prec=0.5, Rec=0.5, F1=0.5
    # Class B: TP=2, FP=1, FN=0 -> Prec=0.6667, Rec=1.0, F1=0.8
    # Class C: TP=1, FP=0, FN=1 -> Prec=1.0, Rec=0.5, F1=0.6667
    metrics = compute_evaluation_metrics(y_true, y_pred, y_proba=None, classes=classes)

    assert metrics["accuracy"] == pytest.approx(4 / 6, abs=1e-3)
    assert metrics["balanced_accuracy"] == pytest.approx((0.5 + 1.0 + 0.5) / 3, abs=1e-3)
    assert metrics["per_class_metrics"]["A"]["precision"] == pytest.approx(0.5, abs=1e-3)
    assert metrics["per_class_metrics"]["B"]["recall"] == pytest.approx(1.0, abs=1e-3)
    assert metrics["confusion_matrix"]["matrix"] == [
        [1, 1, 0],
        [0, 2, 0],
        [1, 0, 1]
    ]


def test_missing_or_invalid_features():
    """Verifies validate_benchmark_dataset raises ValueError on missing features or null values."""
    # 1. Missing required column
    df_missing = pd.DataFrame({
        "feat1": [1.0, 2.0],
        "target": ["A", "B"]
    })
    with pytest.raises(ValueError, match="missing required feature columns"):
        validate_benchmark_dataset(df_missing, expected_features=["feat1", "feat2"], expected_classes=["A", "B"])

    # 2. Null values in features
    df_nulls = pd.DataFrame({
        "feat1": [1.0, np.nan],
        "feat2": [3.0, 4.0],
        "target": ["A", "B"]
    })
    with pytest.raises(ValueError, match="contains null/missing values"):
        validate_benchmark_dataset(df_nulls, expected_features=["feat1", "feat2"], expected_classes=["A", "B"])


def test_unsupported_target_labels():
    """Verifies validate_benchmark_dataset raises ValueError when unexpected target classes appear."""
    df_unknown = pd.DataFrame({
        "feat1": [1.0, 2.0],
        "target": ["A", "UNKNOWN_LABEL"]
    })
    with pytest.raises(ValueError, match="unexpected target labels"):
        validate_benchmark_dataset(df_unknown, expected_features=["feat1"], expected_classes=["A", "B"])


def test_missing_model_artifact():
    """Verifies validate_model_artifact raises FileNotFoundError when artifact does not exist."""
    fake_path = Path("models/non_existent_model_12345.joblib")
    with pytest.raises(FileNotFoundError, match="not found"):
        validate_model_artifact(fake_path)


def test_deterministic_seed_and_benchmark_reproducibility(tmp_path):
    """Verifies that benchmark generation with fixed seed produces identical data and SHA-256."""
    bench_p1 = tmp_path / "bench1.csv"
    bench_p2 = tmp_path / "bench2.csv"

    df1, meta1 = get_or_create_model1_benchmark(bench_p1, num_samples=100, seed=42, force_regenerate=True)
    df2, meta2 = get_or_create_model1_benchmark(bench_p2, num_samples=100, seed=42, force_regenerate=True)

    assert len(df1) == 100
    assert len(df2) == 100
    assert meta1["sha256"] == meta2["sha256"]
    pd.testing.assert_frame_equal(df1, df2)


def test_dummy_baseline_evaluation():
    """Verifies DummyClassifier baseline evaluation produces expected majority-class output."""
    y = pd.Series(["A", "A", "A", "B"])
    res = evaluate_dummy_baseline(y, classes=["A", "B"], strategy="most_frequent")

    assert res["accuracy"] == 0.75
    assert res["per_class_metrics"]["A"]["recall"] == 1.0
    assert res["per_class_metrics"]["B"]["recall"] == 0.0


def test_model1_evaluation_pipeline_execution(tmp_path):
    """Evaluates actual production Model 1 artifact without retraining and verifies metrics."""
    m1_path = MODELS_DIR / "model1_skill_evaluator.joblib"
    assert m1_path.exists(), f"Model 1 artifact missing at {m1_path}"

    res = evaluate_model(m1_path, model_type="model1", output_dir=tmp_path)

    # Core assertions
    assert "model_metrics" in res
    assert "dummy_baseline_metrics" in res
    assert "rule_baseline_metrics" in res
    assert res["model_metrics"]["accuracy"] > 0.80
    assert res["model_metrics"]["macro_f1"] > res["dummy_baseline_metrics"]["macro_f1"]

    # Verify per-class coverage
    for cls_name in MODEL1_CLASSES:
        assert cls_name in res["model_metrics"]["per_class_metrics"]

    # Verify report files were generated
    assert (tmp_path / "model1_evaluation_report.json").exists()
    assert (tmp_path / "model1_evaluation_report.md").exists()


def test_model2_evaluation_and_disagreement_analysis(tmp_path):
    """Evaluates actual production Model 2 artifact and verifies challenger disagreement analysis."""
    m2_path = MODELS_DIR / "model2_final_recommendation.joblib"
    assert m2_path.exists(), f"Model 2 artifact missing at {m2_path}"

    res = evaluate_model(m2_path, model_type="model2", output_dir=tmp_path)

    assert "disagreement_analysis" in res
    disagree = res["disagreement_analysis"]
    assert "disagreement_count" in disagree
    assert "disagreement_rate" in disagree
    assert 0.0 <= disagree["disagreement_rate"] <= 1.0
    assert "disagreement_matrix" in disagree

    # Verify calibration metrics
    cal = res["model_metrics"]["calibration"]
    assert "macro_brier_score" in cal
    assert cal["macro_brier_score"] >= 0.0


def test_model_metadata_record_generation(tmp_path):
    """Verifies that create_model_metadata_record constructs complete, valid JSON audit records."""
    m1_path = MODELS_DIR / "model1_skill_evaluator.joblib"
    res = evaluate_model(m1_path, model_type="model1", output_dir=tmp_path)

    meta_file = tmp_path / "test_meta.json"
    meta = create_model_metadata_record(m1_path, model_type="model1", eval_record=res, output_meta_path=meta_file)

    assert meta_file.exists()
    with open(meta_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)

    assert loaded["artifact_sha256"] == res["model_sha256"]
    assert loaded["input_feature_count"] == 12
    assert loaded["baseline_comparison"]["f1_lift_over_dummy"] > 0.5
    assert "synthetic_notice" in loaded
