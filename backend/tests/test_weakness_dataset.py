"""
TEST SUITE FOR WEAKNESS ML DATASET BUILDER (Step 2)
"""

import copy
import pytest
import pandas as pd
from app.ml.weakness_features import FEATURE_KEYS
from app.ml.weakness_dataset import (
    build_weakness_dataset,
    build_weakness_dataset_dataframe,
    extract_X_y,
    METADATA_KEYS,
    NUMERICAL_FEATURE_KEYS,
    TARGET_LABEL_KEY
)


@pytest.fixture
def sample_assessment_attempts():
    """Returns sample assessment attempt data for multiple skills."""
    return [
        {
            "skill": "Python",
            "required_level": "intermediate",
            "assessed_level": "intermediate",
            "total_score": 0.85,
            "basic_score": 0.90,
            "intermediate_score": 0.80,
            "advanced_score": 0.0,
            "questions_answered_count": 10,
            "answers": [
                {"level": "basic", "is_correct": True, "answered_at": "2026-08-30T10:00:00Z"},
                {"level": "basic", "is_correct": True, "answered_at": "2026-08-30T10:00:10Z"},
                {"level": "intermediate", "is_correct": True, "answered_at": "2026-08-30T10:00:25Z"},
            ],
        },
        {
            "skill": "SQL",
            "required_level": "advanced",
            "assessed_level": "intermediate",  # level gap = 1
            "total_score": 0.70,
            "basic_score": 1.0,
            "intermediate_score": 0.80,
            "advanced_score": 0.20,
            "questions_answered_count": 15,
            "answers": [
                {"level": "basic", "is_correct": True, "answered_at": "2026-08-30T10:05:00Z"},
                {"level": "intermediate", "is_correct": True, "answered_at": "2026-08-30T10:05:15Z"},
            ],
        },
        {
            "skill": "FastAPI",
            "required_level": "basic",
            "assessed_level": "basic",
            "total_score": 0.50,  # score < 0.60 -> weakness = 1
            "basic_score": 0.50,
            "intermediate_score": 0.0,
            "advanced_score": 0.0,
            "questions_answered_count": 5,
            "answers": [
                {"level": "basic", "is_correct": True, "answered_at": "2026-08-30T10:10:00Z"},
                {"level": "basic", "is_correct": False, "answered_at": "2026-08-30T10:10:20Z"},
            ],
        },
    ]


def test_dataset_contains_all_18_feature_keys_plus_target(sample_assessment_attempts):
    """Verify that dataset rows contain all 18 feature keys from FEATURE_KEYS plus target key."""
    dataset = build_weakness_dataset(sample_assessment_attempts)
    assert len(dataset) == 3

    for row in dataset:
        # Check all 18 feature keys are present
        for key in FEATURE_KEYS:
            assert key in row, f"Missing feature key: {key}"

        # Check target label key is present
        assert TARGET_LABEL_KEY in row
        assert row[TARGET_LABEL_KEY] in (0, 1)


def test_one_row_per_assessed_skill(sample_assessment_attempts):
    """Verify dataset output produces exactly one row per assessed skill."""
    dataset = build_weakness_dataset(sample_assessment_attempts)
    assert len(dataset) == len(sample_assessment_attempts)

    skills_in_dataset = [row["skill"] for row in dataset]
    assert skills_in_dataset == ["Python", "SQL", "FastAPI"]


def test_skill_preserved_as_metadata(sample_assessment_attempts):
    """Verify skill is preserved as string metadata and excluded from numerical feature keys."""
    dataset = build_weakness_dataset(sample_assessment_attempts)

    assert "skill" in METADATA_KEYS
    assert "skill" not in NUMERICAL_FEATURE_KEYS
    assert len(NUMERICAL_FEATURE_KEYS) == 17

    X_feats, y_labels, meta_skills = extract_X_y(dataset)
    assert len(X_feats) == 3
    assert len(y_labels) == 3
    assert meta_skills == ["Python", "SQL", "FastAPI"]

    # Verify X feature dicts do NOT contain 'skill'
    for x in X_feats:
        assert "skill" not in x
        assert TARGET_LABEL_KEY not in x
        assert len(x) == 17


def test_target_label_rules_in_dataset(sample_assessment_attempts):
    """Verify correct target label assignments for sample skills."""
    dataset = build_weakness_dataset(sample_assessment_attempts)

    # Python: level_gap=0, total_score=0.85 -> is_weakness = 0
    python_row = next(r for r in dataset if r["skill"] == "Python")
    assert python_row["level_gap"] == 0
    assert python_row["total_score"] == 0.85
    assert python_row[TARGET_LABEL_KEY] == 0

    # SQL: level_gap=1 (>0), total_score=0.70 -> is_weakness = 1
    sql_row = next(r for r in dataset if r["skill"] == "SQL")
    assert sql_row["level_gap"] == 1
    assert sql_row[TARGET_LABEL_KEY] == 1

    # FastAPI: level_gap=0, total_score=0.50 (<0.60) -> is_weakness = 1
    fastapi_row = next(r for r in dataset if r["skill"] == "FastAPI")
    assert fastapi_row["level_gap"] == 0
    assert fastapi_row["total_score"] == 0.50
    assert fastapi_row[TARGET_LABEL_KEY] == 1


def test_no_mutation_of_input_data(sample_assessment_attempts):
    """Verify build_weakness_dataset does not mutate original input data."""
    original_copy = copy.deepcopy(sample_assessment_attempts)
    build_weakness_dataset(sample_assessment_attempts)
    assert sample_assessment_attempts == original_copy


def test_empty_and_invalid_input_handling():
    """Verify graceful empty dataset return for empty/None/invalid inputs."""
    assert build_weakness_dataset([]) == []
    assert build_weakness_dataset(None) == []
    assert build_weakness_dataset("invalid") == []

    df_empty = build_weakness_dataset_dataframe([])
    assert isinstance(df_empty, pd.DataFrame)
    assert len(df_empty) == 0
    assert list(df_empty.columns) == list(FEATURE_KEYS) + [TARGET_LABEL_KEY]


def test_dataframe_dataset_builder(sample_assessment_attempts):
    """Verify build_weakness_dataset_dataframe returns a valid pandas DataFrame."""
    df = build_weakness_dataset_dataframe(sample_assessment_attempts)
    assert isinstance(df, pd.DataFrame)
    assert df.shape == (3, 19)  # 18 features + 1 target column
    assert list(df.columns) == list(FEATURE_KEYS) + [TARGET_LABEL_KEY]
    assert list(df["is_weakness"]) == [0, 1, 1]


def test_compatibility_with_feature_extractor(sample_assessment_attempts):
    """Verify seamless compatibility between feature extractor output and target label generator."""
    from app.ml.weakness_features import build_weakness_features
    from app.ml.weakness_labels import compute_weakness_target_label

    features = build_weakness_features(sample_assessment_attempts)
    labels = [compute_weakness_target_label(f) for f in features]
    assert labels == [0, 1, 1]
