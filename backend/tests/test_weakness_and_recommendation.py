import pytest
from app.services.weakness_service import calculate_weakness
from app.services.recommendation_service import generate_recommendation

def test_calculate_weakness_no_weakness():
    res = calculate_weakness(level_gap=0, total_score=0.85)
    assert not res["is_weakness"]
    assert res["weakness_reason"] == "NONE"

def test_calculate_weakness_level_gap_only():
    res = calculate_weakness(level_gap=1, total_score=0.75)
    assert res["is_weakness"]
    assert res["weakness_reason"] == "LEVEL_GAP"

def test_calculate_weakness_low_score_only():
    res = calculate_weakness(level_gap=0, total_score=0.55)
    assert res["is_weakness"]
    assert res["weakness_reason"] == "LOW_SCORE"

def test_calculate_weakness_both():
    res = calculate_weakness(level_gap=2, total_score=0.35)
    assert res["is_weakness"]
    assert res["weakness_reason"] == "LEVEL_GAP_AND_LOW_SCORE"

def test_generate_recommendation_low_priority():
    res = generate_recommendation(
        skill="Python",
        required_level="advanced",
        assessed_level="advanced",
        level_gap=0,
        total_score=0.85,
        is_weakness=False,
        weakness_reason="NONE"
    )
    assert res["priority"] == "LOW"
    assert "Continue practicing" in res["recommendation"]

def test_generate_recommendation_medium_priority():
    res = generate_recommendation(
        skill="Python",
        required_level="intermediate",
        assessed_level="basic",
        level_gap=1,
        total_score=0.70,
        is_weakness=True,
        weakness_reason="LEVEL_GAP"
    )
    assert res["priority"] == "MEDIUM"
    assert "Targeted practice required" in res["recommendation"]

def test_generate_recommendation_high_priority_gap_2():
    res = generate_recommendation(
        skill="Python",
        required_level="advanced",
        assessed_level="basic",
        level_gap=2,
        total_score=0.70,
        is_weakness=True,
        weakness_reason="LEVEL_GAP"
    )
    assert res["priority"] == "HIGH"
    
def test_generate_recommendation_high_priority_low_score():
    res = generate_recommendation(
        skill="Python",
        required_level="basic",
        assessed_level="basic",
        level_gap=0,
        total_score=0.35,
        is_weakness=True,
        weakness_reason="LOW_SCORE"
    )
    assert res["priority"] == "HIGH"
    assert "Review weak areas" in res["recommendation"]

def test_generate_recommendation_high_priority_gap_and_moderate_score():
    res = generate_recommendation(
        skill="Python",
        required_level="intermediate",
        assessed_level="basic",
        level_gap=1,
        total_score=0.50,
        is_weakness=True,
        weakness_reason="LEVEL_GAP_AND_LOW_SCORE"
    )
    assert res["priority"] == "HIGH"
    assert "Immediate foundational review" in res["recommendation"]
