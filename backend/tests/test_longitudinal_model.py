import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from app.ml.longitudinal_model import (
    train_longitudinal_model, 
    validate_dataset, 
    InsufficientTrainingDataError
)

def test_validate_dataset_insufficient_samples():
    X = pd.DataFrame({"feat1": range(5)})
    y = pd.Series([0, 1, 0, 1, 0])
    
    with pytest.raises(InsufficientTrainingDataError, match="only 5 samples"):
        validate_dataset(X, y)

def test_validate_dataset_missing_class():
    X = pd.DataFrame({"feat1": range(15)})
    y = pd.Series([0]*15) # Only one class
    
    with pytest.raises(InsufficientTrainingDataError, match="target has 1 classes"):
        validate_dataset(X, y)

@patch("app.ml.longitudinal_model.build_longitudinal_dataset")
def test_train_longitudinal_model_empty_data(mock_build_dataset):
    # Setup mock to return empty dataframe with appropriate columns
    mock_build_dataset.return_value = pd.DataFrame(columns=["improved"])
    
    db = MagicMock()
    with pytest.raises(InsufficientTrainingDataError, match="No longitudinal data available"):
        train_longitudinal_model(db)

@patch("app.ml.longitudinal_model.build_longitudinal_dataset")
def test_train_longitudinal_model_only_negative_data(mock_build_dataset):
    # Simulated current state: many records but no positive improvement outcomes
    records = []
    for i in range(15):
        records.append({
            "user_id": i,
            "skill": "python",
            "previous_total_score": 0.8,
            "previous_basic_score": 0.8,
            "previous_intermediate_score": 0.0,
            "previous_advanced_score": 0.0,
            "previous_required_level": "basic",
            "previous_assessed_level": "basic",
            "previous_level_gap": 0,
            "previous_is_weakness": False,
            "improved": False # Only false!
        })
    mock_build_dataset.return_value = pd.DataFrame(records)
    
    db = MagicMock()
    # Should raise error about lacking classes
    with pytest.raises(InsufficientTrainingDataError, match="target has 1 classes"):
        train_longitudinal_model(db)

@patch("app.ml.longitudinal_model.build_longitudinal_dataset")
def test_train_longitudinal_model_success_with_valid_data(mock_build_dataset):
    # Simulated future state: valid data exists
    records = []
    for i in range(20):
        records.append({
            "user_id": i, # Distinct users
            "skill": "python",
            "previous_total_score": 0.5 if i % 2 == 0 else 0.8,
            "previous_basic_score": 0.8,
            "previous_intermediate_score": 0.0,
            "previous_advanced_score": 0.0,
            "previous_required_level": "basic",
            "previous_assessed_level": "basic",
            "previous_level_gap": 0,
            "previous_is_weakness": False,
            "improved": i % 2 == 0 # Alternating True/False
        })
    mock_build_dataset.return_value = pd.DataFrame(records)
    
    db = MagicMock()
    result = train_longitudinal_model(db)
    
    assert result["status"] == "SUCCESS"
    assert result["samples"] == 20
    assert result["positive_class_ratio"] == 0.5
    assert "logistic_regression" in result
    assert "random_forest" in result
    assert "accuracy" in result["logistic_regression"]
