"""
Unit tests for Synthetic Overall Job Readiness Dataset Generator (app/ml/generate_overall_dataset.py)
"""

from pathlib import Path
import pytest
import pandas as pd
import numpy as np

from app.ml.overall_features import DEFAULT_FEATURE_KEYS
from app.ml.generate_overall_dataset import (
    generate_overall_dataset,
    compute_synthetic_target_label,
    main,
    DEFAULT_OUTPUT_PATH,
    READINESS_LEVELS
)


def test_generate_overall_dataset_shape_and_columns():
    """Test that generated dataset has requested rows, 14 feature columns, and target column."""
    num_samples = 300
    df = generate_overall_dataset(num_samples=num_samples, random_seed=42)

    assert len(df) == num_samples
    assert df.shape[1] == 15  # 14 features + 1 target

    expected_columns = list(DEFAULT_FEATURE_KEYS) + ["overall_readiness"]
    assert list(df.columns) == expected_columns


def test_generate_overall_dataset_reproducibility():
    """Test that dataset generation is strictly reproducible with the same random seed."""
    df1 = generate_overall_dataset(num_samples=100, random_seed=42)
    df2 = generate_overall_dataset(num_samples=100, random_seed=42)

    pd.testing.assert_frame_equal(df1, df2)


def test_feature_value_constraints():
    """Test that generated features satisfy expected numerical range constraints."""
    df = generate_overall_dataset(num_samples=200, random_seed=42)

    # Check ratio features are within [0.0, 1.0]
    ratio_cols = [
        "cv_match_ratio",
        "required_skills_match_ratio",
        "preferred_skills_match_ratio",
        "assessed_skills_ratio",
        "required_assessment_coverage",
        "avg_assessment_score",
        "zero_gap_skills_ratio",
        "ml_meets_req_ratio",
        "cv_matching_score",
    ]
    for col in ratio_cols:
        assert (df[col] >= 0.0).all(), f"Feature {col} has negative values"
        assert (df[col] <= 1.0).all(), f"Feature {col} exceeds 1.0"

    # Check non-negative counts and gap metrics
    assert (df["total_skill_count"] >= 0).all()
    assert (df["required_skill_count"] >= 0).all()
    assert (df["preferred_skill_count"] >= 0).all()
    assert (df["avg_level_gap"] >= 0.0).all()
    assert (df["max_level_gap"] >= 0.0).all()


def test_target_label_distribution_and_validity():
    """Test that overall_readiness labels are non-trivial, non-null, and contain all 3 classes."""
    df = generate_overall_dataset(num_samples=400, random_seed=42)

    # Check no nulls
    assert df["overall_readiness"].isnull().sum() == 0

    # Check valid label set
    unique_labels = set(df["overall_readiness"].unique())
    assert unique_labels.issubset(set(READINESS_LEVELS))

    # Check that all 3 classes ('low', 'medium', 'high') are present
    assert unique_labels == {"low", "medium", "high"}

    # Check non-trivial distribution (each class should have at least 10% representation)
    class_counts = df["overall_readiness"].value_counts()
    for level in READINESS_LEVELS:
        assert class_counts[level] > (0.10 * len(df)), f"Class {level} is underrepresented"


def test_compute_synthetic_target_label_logic():
    """Test target label calculation function for strong vs weak candidate profiles."""
    high_candidate_features = {
        "required_skills_match_ratio": 1.0,
        "avg_assessment_score": 0.95,
        "cv_matching_score": 0.90,
        "ml_meets_req_ratio": 1.0,
        "zero_gap_skills_ratio": 1.0,
        "avg_level_gap": 0.0,
    }
    low_candidate_features = {
        "required_skills_match_ratio": 0.1,
        "avg_assessment_score": 0.20,
        "cv_matching_score": 0.15,
        "ml_meets_req_ratio": 0.0,
        "zero_gap_skills_ratio": 0.0,
        "avg_level_gap": 2.0,
    }

    high_labels = [compute_synthetic_target_label(high_candidate_features) for _ in range(20)]
    low_labels = [compute_synthetic_target_label(low_candidate_features) for _ in range(20)]

    # Strong feature profile should consistently produce 'high' or 'medium'
    assert "low" not in high_labels
    # Weak feature profile should consistently produce 'low'
    assert "high" not in low_labels


def test_cli_main_generates_csv(tmp_path, monkeypatch):
    """Test that main() successfully writes the dataset CSV to file."""
    output_file = tmp_path / "test_overall_training_data.csv"
    monkeypatch.setattr("app.ml.generate_overall_dataset.DEFAULT_OUTPUT_PATH", output_file)
    monkeypatch.setattr("app.ml.generate_overall_dataset.DEFAULT_DATA_DIR", tmp_path)

    main()

    assert output_file.exists()
    df_loaded = pd.read_csv(output_file)
    assert len(df_loaded) == 500
    assert "overall_readiness" in df_loaded.columns
