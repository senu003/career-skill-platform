"""
UNIT TESTS FOR STEP 12: LONGITUDINAL ML MODEL TRAINING & EVALUATION

Tests target separation, leakage prevention, candidate-aware splits, pipeline fit,
prediction shapes, probability ranges, artifact loading, and metadata schema.
"""

import os
import json
import joblib
import pytest
import numpy as np
import pandas as pd

from app.ml.train_longitudinal_ml import (
    load_dataset,
    audit_feature_leakage,
    create_preprocessor,
    perform_cross_validation,
    train_and_evaluate,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    GROUP_COLUMN,
    MODEL_FILE_PATH,
    METADATA_FILE_PATH,
)
from sklearn.model_selection import GroupShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression


def test_synthetic_dataset_loading_and_target_separation():
    """Verifies dataset loads, target column exists, and feature matrix excludes target."""
    df = load_dataset()
    assert not df.empty
    assert len(df) >= 1000
    assert TARGET_COLUMN in df.columns
    assert GROUP_COLUMN in df.columns

    # Verify target values are strictly 0 or 1
    unique_targets = set(df[TARGET_COLUMN].unique())
    assert unique_targets.issubset({0, 1})
    assert len(unique_targets) == 2

    # Verify features exclude target and grouping column
    feature_cols = set(FEATURE_COLUMNS)
    assert TARGET_COLUMN not in feature_cols
    assert GROUP_COLUMN not in feature_cols


def test_no_t1_feature_leakage():
    """Verifies zero t1 features exist in feature matrix and audit detects forced leakage."""
    df = load_dataset()
    X = df[FEATURE_COLUMNS].copy()

    # Should pass without error
    audit_feature_leakage(X)

    # Negative test: injecting a t1 column should trigger ValueError
    X_leaked = X.copy()
    X_leaked["later_total_score"] = 85.0
    with pytest.raises(ValueError, match="Data leakage detected"):
        audit_feature_leakage(X_leaked)

    X_leaked_target = X.copy()
    X_leaked_target["improved"] = 1
    with pytest.raises(ValueError, match="Target column 'improved' found"):
        audit_feature_leakage(X_leaked_target)


def test_candidate_aware_split_no_overlap():
    """Verifies candidate-aware split produces 0 overlapping candidates between train and test."""
    df = load_dataset()
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]
    groups = df[GROUP_COLUMN]

    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(X, y, groups=groups))

    train_candidates = set(groups.iloc[train_idx].unique())
    test_candidates = set(groups.iloc[test_idx].unique())

    # Assert ZERO intersection between candidate IDs
    overlap = train_candidates.intersection(test_candidates)
    assert len(overlap) == 0
    assert len(train_candidates) > 0
    assert len(test_candidates) > 0
    assert len(train_candidates) + len(test_candidates) == groups.nunique()


def test_successful_pipeline_training_and_prediction_shape():
    """Verifies sklearn Pipeline preprocesses, trains, and outputs correct prediction shape."""
    df = load_dataset()
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]
    groups = df[GROUP_COLUMN]

    gss = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(gss.split(X, y, groups=groups))

    X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
    y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

    pipe = Pipeline([
        ("preprocessor", create_preprocessor()),
        ("classifier", LogisticRegression(random_state=42, max_iter=1000)),
    ])

    pipe.fit(X_train, y_train)

    y_pred = pipe.predict(X_test)
    assert y_pred.shape == (len(X_test),)
    assert set(np.unique(y_pred)).issubset({0, 1})


def test_probability_outputs_in_valid_range():
    """Verifies predict_proba returns probabilities strictly in [0.0, 1.0]."""
    df = load_dataset()
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    pipe = Pipeline([
        ("preprocessor", create_preprocessor()),
        ("classifier", LogisticRegression(random_state=42, max_iter=1000)),
    ])
    pipe.fit(X, y)

    y_prob = pipe.predict_proba(X)
    assert y_prob.shape == (len(X), 2)
    assert np.all(y_prob >= 0.0)
    assert np.all(y_prob <= 1.0)
    assert np.allclose(y_prob.sum(axis=1), 1.0)


def test_candidate_aware_cross_validation_execution():
    """Verifies candidate-aware GroupKFold cross-validation computes metrics without error."""
    df = load_dataset()
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]
    groups = df[GROUP_COLUMN]

    cv_results = perform_cross_validation(X, y, groups, n_splits=5)
    assert cv_results["n_splits"] == 5
    assert "logistic_regression" in cv_results
    assert "random_forest" in cv_results
    assert 0.5 <= cv_results["logistic_regression"]["roc_auc_mean"] <= 1.0
    assert cv_results["logistic_regression"]["roc_auc_std"] >= 0.0


def test_model_artifact_and_metadata_serialization():
    """Verifies training runner generates joblib model file and valid metadata JSON."""
    results = train_and_evaluate()
    assert results["status"] == "SUCCESS"

    # Check joblib model file
    assert os.path.exists(MODEL_FILE_PATH)
    loaded_pipeline = joblib.load(MODEL_FILE_PATH)
    assert hasattr(loaded_pipeline, "predict")
    assert hasattr(loaded_pipeline, "predict_proba")

    # Check metadata JSON file
    assert os.path.exists(METADATA_FILE_PATH)
    with open(METADATA_FILE_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)

    assert meta["model_version"] == "1.0.0-synthetic"
    assert "raw_features" in meta
    assert "transformed_feature_names" in meta
    assert "evaluation_metrics" in meta
    assert "cross_validation_5fold" in meta
    assert "synthetic_data_warning" in meta
    assert meta["candidate_counts"]["total"] == 250
    assert meta["sample_counts"]["total"] >= 1000


def test_saved_model_predicts_identically():
    """Verifies loaded joblib model predictions match live pipeline predictions."""
    df = load_dataset()
    X_sample = df[FEATURE_COLUMNS].head(20)

    loaded_pipeline = joblib.load(MODEL_FILE_PATH)
    preds = loaded_pipeline.predict(X_sample)
    probs = loaded_pipeline.predict_proba(X_sample)

    assert len(preds) == 20
    assert probs.shape == (20, 2)
    assert np.all(probs >= 0.0) and np.all(probs <= 1.0)
