"""
Tests for ML Pipeline: Dataset generation, model training, predictor, and invalid input handling.
"""

from pathlib import Path
import pytest
import pandas as pd
import numpy as np

from app.ml.generate_dataset import generate_synthetic_dataset, DEFAULT_OUTPUT_PATH
from app.ml.train_model import (
    train_and_evaluate,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
    CLASSES,
    build_pipeline,
)
from app.ml.predict import SkillLevelPredictor, predict_skill_level


def test_dataset_generation():
    """Test synthetic dataset generation schema, shapes, missing values, and target classes."""
    df = generate_synthetic_dataset(num_samples=500, random_seed=42)

    # 1. Dataset size
    assert len(df) == 500

    # 2. Expected columns
    expected_cols = set(FEATURE_COLUMNS + [TARGET_COLUMN])
    assert set(df.columns) == expected_cols

    # 3. Target classes
    unique_targets = set(df[TARGET_COLUMN].unique())
    assert unique_targets == set(CLASSES)

    # Reasonable representation of all 3 classes
    counts = df[TARGET_COLUMN].value_counts()
    for cls_name in CLASSES:
        assert counts[cls_name] >= 100

    # 4. No missing values
    assert df.isnull().sum().sum() == 0

    # Score bounds [0.0, 1.0]
    for col in ["basic_score", "intermediate_score", "advanced_score", "total_score"]:
        assert (df[col] >= 0.0).all()
        assert (df[col] <= 1.0).all()


def test_model_training(tmp_path):
    """Test model training script execution, metrics generation, and model file saving."""
    data_file = tmp_path / "test_data.csv"
    model_file = tmp_path / "test_model.joblib"

    # Generate test dataset
    df = generate_synthetic_dataset(num_samples=300, random_seed=123)
    df.to_csv(data_file, index=False)

    # Run training
    metrics, pipeline = train_and_evaluate(
        data_path=data_file,
        model_output_path=model_file,
        random_seed=123
    )

    # Verify metrics structure
    assert metrics["dataset_size"] == 300
    assert metrics["train_size"] == 240
    assert metrics["test_size"] == 60
    assert 0.0 <= metrics["test_accuracy"] <= 1.0
    assert 0.0 <= metrics["test_f1_macro"] <= 1.0

    # Confusion matrix shape (3x3)
    cm = metrics["confusion_matrix"]
    assert len(cm) == 3
    assert all(len(row) == 3 for row in cm)

    # Model file saved
    assert model_file.exists()


def test_prediction_output(tmp_path):
    """Test prediction output structure and probability outputs."""
    data_file = tmp_path / "test_data.csv"
    model_file = tmp_path / "test_model.joblib"

    df = generate_synthetic_dataset(num_samples=150, random_seed=42)
    df.to_csv(data_file, index=False)
    train_and_evaluate(data_path=data_file, model_output_path=model_file)

    predictor = SkillLevelPredictor(model_path=model_file)

    sample_input = {
        "cv_matched": True,
        "required_level": "intermediate",
        "importance": "required",
        "basic_score": 0.90,
        "intermediate_score": 0.85,
        "advanced_score": 0.40,
        "total_score": 0.72,
    }

    result = predictor.predict_single(sample_input)
    assert "predicted_level" in result
    assert result["predicted_level"] in CLASSES
    assert "probabilities" in result

    # Probabilities sum to ~1.0
    probs = result["probabilities"]
    assert set(probs.keys()) == set(CLASSES)
    assert pytest.approx(sum(probs.values()), abs=1e-2) == 1.0

    # Convenience function check
    level_str = predict_skill_level(sample_input, model_path=model_file)
    assert level_str in CLASSES


def test_invalid_input_handling(tmp_path):
    """Test error handling for invalid feature inputs."""
    data_file = tmp_path / "test_data.csv"
    model_file = tmp_path / "test_model.joblib"

    df = generate_synthetic_dataset(num_samples=150, random_seed=42)
    df.to_csv(data_file, index=False)
    train_and_evaluate(data_path=data_file, model_output_path=model_file)

    predictor = SkillLevelPredictor(model_path=model_file)

    # 1. Non-dict input
    with pytest.raises(ValueError, match="Input must be a dictionary"):
        predictor.predict_single("not a dict")

    # 2. Missing feature
    incomplete = {
        "cv_matched": True,
        "required_level": "basic",
        # missing importance & score fields
    }
    with pytest.raises(ValueError, match="Missing required input features"):
        predictor.predict_single(incomplete)

    # 3. Invalid score bounds
    invalid_score = {
        "cv_matched": True,
        "required_level": "intermediate",
        "importance": "required",
        "basic_score": 1.5,  # Invalid: > 1.0
        "intermediate_score": 0.8,
        "advanced_score": 0.4,
        "total_score": 0.7,
    }
    with pytest.raises(ValueError, match="must be between 0.0 and 1.0"):
        predictor.predict_single(invalid_score)

    # 4. Invalid categorical level
    invalid_cat = {
        "cv_matched": True,
        "required_level": "god_mode",  # Invalid
        "importance": "required",
        "basic_score": 0.5,
        "intermediate_score": 0.5,
        "advanced_score": 0.5,
        "total_score": 0.5,
    }
    with pytest.raises(ValueError, match="required_level must be one of"):
        predictor.predict_single(invalid_cat)
