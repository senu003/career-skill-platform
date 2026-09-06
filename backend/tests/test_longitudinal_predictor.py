"""
TEST SUITE FOR STEP 13: LONGITUDINAL ML MODEL INTEGRATION

Tests:
- Model artifact loading
- Feature safety & t1 data leakage auditing
- Probability prediction range [0.0, 1.0]
- Valid history prediction & single-assessment null behavior
- Preservation of deterministic weakness and recommendation outputs
- Per-skill and overall candidate aggregation
- Safe exception handling
"""

import pytest
import numpy as np
import pandas as pd

from app.ml.longitudinal_predictor import (
    LongitudinalImprovementPredictor,
    predict_improvement_probability,
    FEATURE_COLUMNS,
    FORBIDDEN_T1_SUBSTRINGS
)
from app.schemas.skill_analysis import FinalSkillItemSchema, AssessmentResultSchema
from app.schemas.aggregation import FinalAssessmentAggregationSchema
from app.services.aggregation_service import aggregate_final_assessment
from app.services.weakness_service import calculate_weakness
from app.services.recommendation_service import generate_recommendation


def test_model_loading_and_singleton():
    """Confirms the longitudinal improvement model loads successfully via singleton."""
    predictor1 = LongitudinalImprovementPredictor()
    predictor2 = LongitudinalImprovementPredictor()

    assert predictor1 is predictor2
    assert predictor1.model is not None, "Longitudinal model pipeline should be loaded."


def test_feature_ordering_and_columns():
    """Confirms expected feature list and ordering matches training schema."""
    expected = [
        "previous_assessed_level",
        "required_level",
        "previous_priority",
        "previous_total_score",
        "previous_level_gap",
        "cv_match_score",
        "previous_is_weakness",
        "days_between_attempts",
        "previous_basic_score",
        "previous_intermediate_score",
        "previous_advanced_score",
    ]
    assert FEATURE_COLUMNS == expected, f"Feature columns order mismatch: {FEATURE_COLUMNS}"


def test_valid_t0_prediction_and_range():
    """Tests prediction with valid t0 historical data returns probability bounded in [0.0, 1.0]."""
    t0_data = {
        "previous_assessed_level": "intermediate",
        "required_level": "advanced",
        "previous_priority": "High",
        "previous_total_score": 0.55,
        "previous_level_gap": 1,
        "cv_match_score": 85.0,
        "previous_is_weakness": True,
        "days_between_attempts": 30.0,
        "previous_basic_score": 0.90,
        "previous_intermediate_score": 0.60,
        "previous_advanced_score": 0.20,
    }

    prob = predict_improvement_probability(t0_data)
    assert prob is not None, "Valid t0 features should produce non-null prediction."
    assert isinstance(prob, float)
    assert 0.0 <= prob <= 1.0, f"Probability {prob} out of valid range [0.0, 1.0]"


def test_insufficient_history_returns_null():
    """Confirms single-assessment or missing t0 history returns null (None)."""
    assert predict_improvement_probability(None) is None
    assert predict_improvement_probability({}) is None
    assert predict_improvement_probability({"skill": "Python"}) is None


def test_leakage_audit_rejects_t1_features():
    """Confirms error is raised if t1 features are leaked into inference call."""
    predictor = LongitudinalImprovementPredictor()

    leaked_inputs = [
        {"later_total_score": 0.85, "previous_assessed_level": "basic", "required_level": "basic"},
        {"later_level": "advanced", "previous_assessed_level": "basic", "required_level": "basic"},
        {"improved": 1, "previous_assessed_level": "basic", "required_level": "basic"},
        {"declined": 0, "previous_assessed_level": "basic", "required_level": "basic"},
        {"score_change": 0.15, "previous_assessed_level": "basic", "required_level": "basic"},
        {"persistent_weakness": False, "previous_assessed_level": "basic", "required_level": "basic"},
    ]

    for leaked_dict in leaked_inputs:
        with pytest.raises(ValueError, match="Data leakage detected"):
            predictor.audit_t0_feature_leakage(leaked_dict)

        # Confirm predict_probability safely handles/catches it and returns None
        assert predictor.predict_probability(leaked_dict) is None


def test_deterministic_logic_remains_unchanged():
    """Confirms deterministic weakness and recommendation rules are untouched by ML model."""
    level_gap = 1
    total_score = 0.50

    weakness_info = calculate_weakness(level_gap=level_gap, total_score=total_score)
    assert weakness_info["is_weakness"] is True
    assert weakness_info["weakness_reason"] == "LEVEL_GAP_AND_LOW_SCORE"

    rec_info = generate_recommendation(
        skill="Python",
        required_level="advanced",
        assessed_level="intermediate",
        level_gap=level_gap,
        total_score=total_score,
        is_weakness=weakness_info["is_weakness"],
        weakness_reason=weakness_info["weakness_reason"]
    )
    assert rec_info["priority"] == "HIGH"
    assert "Python" in rec_info["recommendation"]
    assert "advanced" in rec_info["recommendation"]


def test_aggregation_with_multiple_skills():
    """Tests candidate aggregation calculates correct mean of valid per-skill probabilities."""
    skill1 = FinalSkillItemSchema(
        skill="Python",
        required_level="advanced",
        importance="required",
        matched=True,
        assessed_level="intermediate",
        total_score=0.70,
        level_gap=1,
        is_weakness=True,
        weakness_reason="LEVEL_GAP",
        priority="HIGH",
        recommendation="Study advanced Python",
        recommendation_reason="Level gap detected",
        improvement_probability=0.60
    )

    skill2 = FinalSkillItemSchema(
        skill="SQL",
        required_level="intermediate",
        importance="required",
        matched=True,
        assessed_level="intermediate",
        total_score=0.85,
        level_gap=0,
        is_weakness=False,
        weakness_reason="NONE",
        priority="LOW",
        recommendation="Maintain current skill level",
        recommendation_reason="Meets requirement",
        improvement_probability=0.80
    )

    skill3 = FinalSkillItemSchema(
        skill="Docker",
        required_level="basic",
        importance="preferred",
        matched=False,
        assessed_level=None,
        total_score=None,
        level_gap=None,
        is_weakness=False,
        weakness_reason="NONE",
        priority="LOW",
        recommendation="Take basic assessment",
        recommendation_reason="Not assessed",
        improvement_probability=None
    )

    aggregated = aggregate_final_assessment([skill1, skill2, skill3])
    assert aggregated.overall_improvement_probability == 0.70
    assert aggregated.skills[0].improvement_probability == 0.60
    assert aggregated.skills[1].improvement_probability == 0.80
    assert aggregated.skills[2].improvement_probability is None


def test_aggregation_with_no_ml_predictions():
    """Tests overall_improvement_probability is null when no per-skill predictions exist."""
    skill1 = FinalSkillItemSchema(
        skill="Python",
        required_level="intermediate",
        importance="required",
        matched=True,
        assessed_level="intermediate",
        total_score=0.75,
        level_gap=0,
        is_weakness=False,
        weakness_reason="NONE",
        priority="LOW",
        recommendation="Maintain current level",
        recommendation_reason="Meets requirement",
        improvement_probability=None
    )

    aggregated = aggregate_final_assessment([skill1])
    assert aggregated.overall_improvement_probability is None


def test_model_failure_safety():
    """Confirms inference returns None gracefully when an error occurs."""
    predictor = LongitudinalImprovementPredictor()
    # Pass invalid data type
    res = predictor.predict_probability({"previous_assessed_level": "INVALID_LEVEL", "required_level": None})
    assert res is None
