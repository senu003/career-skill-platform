"""
TEST SUITE FOR SYNTHETIC LONGITUDINAL ML DATASET (STEP 11)

Verifies:
1. Reproducibility with fixed random seed
2. Strict target calculation (improved = 1 if later_total_score > previous_total_score else 0)
3. Class balance and presence of both target classes (0 and 1)
4. Valid score ranges [0.0, 100.0]
5. Valid level bounds [1, 3]
6. Zero data leakage (leakage audit validation)
7. Presence of all required t0 features without missing values
8. Absence of duplicate candidate-skill attempt pairs
"""

import pytest
import pandas as pd
import numpy as np

from app.ml.synthetic.generator import (
    generate_synthetic_longitudinal_dataset,
    get_feature_matrix,
    REQUIRED_T0_FEATURES,
)
from app.ml.synthetic.leakage_audit import (
    validate_synthetic_dataset_leakage,
    audit_feature_matrix,
    LeakageAuditError,
)
from app.ml.synthetic.quality_checks import run_dataset_quality_checks


def test_synthetic_dataset_reproducibility():
    """Verifies that generation with a fixed seed produces identical DataFrames."""
    df1 = generate_synthetic_longitudinal_dataset(num_candidates=100, seed=42)
    df2 = generate_synthetic_longitudinal_dataset(num_candidates=100, seed=42)
    
    assert len(df1) == len(df2), "Row counts must match for same seed"
    pd.testing.assert_frame_equal(df1, df2), "Generated DataFrames must be 100% identical with same seed"


def test_synthetic_dataset_reproducibility_different_seeds():
    """Verifies that different random seeds produce different progression datasets."""
    df1 = generate_synthetic_longitudinal_dataset(num_candidates=100, seed=42)
    df2 = generate_synthetic_longitudinal_dataset(num_candidates=100, seed=999)
    
    assert not df1.equals(df2), "Different seeds should produce different datasets"


def test_strict_target_calculation():
    """Verifies that target 'improved' is strictly 1 if later_total_score > previous_total_score, else 0."""
    df = generate_synthetic_longitudinal_dataset(num_candidates=150, seed=42)
    
    expected_improved = (df["later_total_score"] > df["previous_total_score"]).astype(int)
    
    # Assert exact match across all rows
    assert (df["improved"] == expected_improved).all(), (
        "Target 'improved' must strictly equal (later_total_score > previous_total_score)"
    )


def test_both_classes_exist_and_balanced():
    """Verifies that both target classes (0 and 1) exist in meaningful proportions."""
    df = generate_synthetic_longitudinal_dataset(num_candidates=250, seed=42)
    
    class_counts = df["improved"].value_counts().to_dict()
    
    assert 0 in class_counts, "Target class 0 (not improved) must exist"
    assert 1 in class_counts, "Target class 1 (improved) must exist"
    
    ratio = df["improved"].mean()
    # Require ratio between 30% and 70% to ensure meaningful non-trivial experimentation
    assert 0.30 <= ratio <= 0.70, f"Class distribution should be balanced, got improvement rate of {ratio:.2%}"


def test_valid_score_ranges():
    """Verifies that all score columns remain within the valid [0.0, 100.0] range."""
    df = generate_synthetic_longitudinal_dataset(num_candidates=150, seed=42)
    
    score_cols = [
        "previous_total_score",
        "later_total_score",
        "previous_basic_score",
        "previous_intermediate_score",
        "previous_advanced_score",
        "cv_match_score",
    ]
    
    for col in score_cols:
        assert (df[col] >= 0.0).all(), f"Column '{col}' has values < 0.0"
        assert (df[col] <= 100.0).all(), f"Column '{col}' has values > 100.0"


def test_valid_level_bounds():
    """Verifies that required and assessed levels are valid integers in [1, 3]."""
    df = generate_synthetic_longitudinal_dataset(num_candidates=150, seed=42)
    
    level_cols = ["previous_assessed_level", "required_level", "later_assessed_level"]
    
    for col in level_cols:
        assert df[col].isin([1, 2, 3]).all(), f"Column '{col}' contains values outside valid levels [1, 2, 3]"


def test_no_missing_required_features():
    """Verifies that all required t0 features are present and contain zero missing values."""
    df = generate_synthetic_longitudinal_dataset(num_candidates=150, seed=42)
    feature_df = get_feature_matrix(df)
    
    for feat in REQUIRED_T0_FEATURES:
        assert feat in feature_df.columns, f"Required feature '{feat}' missing from feature matrix"
        assert feature_df[feat].isnull().sum() == 0, f"Feature '{feat}' contains missing values"


def test_no_duplicate_longitudinal_rows():
    """Verifies that no candidate-skill attempt pairs are duplicated."""
    df = generate_synthetic_longitudinal_dataset(num_candidates=200, seed=42)
    
    duplicate_count = df.duplicated(subset=["candidate_id", "skill", "attempt_pair_id"]).sum()
    assert duplicate_count == 0, f"Found {duplicate_count} duplicate longitudinal attempt pair rows"


def test_leakage_audit_pass():
    """Verifies that feature matrix passes automated data leakage audit."""
    df = generate_synthetic_longitudinal_dataset(num_candidates=150, seed=42)
    
    audit_res = validate_synthetic_dataset_leakage(df)
    assert audit_res["passed_leakage_audit"] is True, "Automated leakage audit must pass"


def test_leakage_audit_detects_future_column():
    """Verifies that leakage auditor detects if a t1 column is accidentally injected."""
    df = generate_synthetic_longitudinal_dataset(num_candidates=50, seed=42)
    feature_df = get_feature_matrix(df)
    
    # Intentionally inject a future column
    corrupted_df = feature_df.copy()
    corrupted_df["later_score"] = df["later_total_score"]
    
    with pytest.raises(LeakageAuditError) as exc_info:
        audit_feature_matrix(corrupted_df)
        
    assert "DATA LEAKAGE DETECTED" in str(exc_info.value)
    assert "later_score" in str(exc_info.value)


def test_quality_checks_summary():
    """Verifies quality check execution and structured metric generation."""
    df = generate_synthetic_longitudinal_dataset(num_candidates=100, seed=42)
    qc = run_dataset_quality_checks(df)
    
    assert qc["total_rows"] == len(df)
    assert qc["unique_candidates"] == 100
    assert qc["total_missing_values"] == 0
    assert qc["duplicate_rows"] == 0
    assert "improved_0" in qc["class_distribution"]
    assert "improved_1" in qc["class_distribution"]
