"""
Unit tests for Overall Job Readiness Feature Engineering module (app/ml/overall_features.py)
"""

import pytest
from app.ml.overall_features import build_overall_features, DEFAULT_FEATURE_KEYS


def test_expected_fixed_14_feature_keys():
    """Test that the returned dictionary contains exactly the 14 expected feature keys."""
    sample_input = {
        "skills": [
            {
                "skill": "Python",
                "required_level": "intermediate",
                "importance": "required",
                "matched": True,
                "assessed_level": "intermediate",
                "ml_predicted_level": "intermediate",
                "level_gap": 0,
                "total_score": 0.85
            }
        ],
        "score_data": {"score": 100.0}
    }
    feats = build_overall_features(sample_input)
    assert set(feats.keys()) == set(DEFAULT_FEATURE_KEYS)
    assert len(feats) == 14


def test_normal_candidate_multiple_skills():
    """Test normal candidate with multiple required and preferred skills."""
    combined_data = {
        "matched_skills": [],
        "missing_skills": [],
        "skills": [
            {
                "skill": "Python",
                "required_level": "intermediate",
                "importance": "required",
                "matched": True,
                "assessed_level": "advanced",
                "ml_predicted_level": "advanced",
                "level_gap": 0,
                "total_score": 0.90
            },
            {
                "skill": "SQL",
                "required_level": "basic",
                "importance": "required",
                "matched": True,
                "assessed_level": "basic",
                "ml_predicted_level": "basic",
                "level_gap": 0,
                "total_score": 0.70
            },
            {
                "skill": "Docker",
                "required_level": "basic",
                "importance": "preferred",
                "matched": False,
                "assessed_level": None,
                "ml_predicted_level": None,
                "level_gap": None
            }
        ],
        "score_data": {"score": 66.67}
    }

    feats = build_overall_features(combined_data)

    assert feats["total_skill_count"] == 3.0
    assert feats["required_skill_count"] == 2.0
    assert feats["preferred_skill_count"] == 1.0
    assert pytest.approx(feats["cv_match_ratio"], abs=1e-3) == 0.6667
    assert feats["required_skills_match_ratio"] == 1.0  # 2 of 2 required skills matched
    assert feats["preferred_skills_match_ratio"] == 0.0  # 0 of 1 preferred skills matched
    assert pytest.approx(feats["assessed_skills_ratio"], abs=1e-3) == 0.6667  # 2 of 3 assessed
    assert feats["required_assessment_coverage"] == 1.0  # 2 of 2 required assessed
    assert pytest.approx(feats["avg_assessment_score"], abs=1e-3) == 0.80  # (0.90 + 0.70) / 2
    assert feats["avg_level_gap"] == 0.0
    assert feats["max_level_gap"] == 0.0
    assert feats["zero_gap_skills_ratio"] == 1.0
    assert feats["ml_meets_req_ratio"] == 1.0  # Python (adv>=inter) and SQL (basic>=basic)
    assert pytest.approx(feats["cv_matching_score"], abs=1e-3) == 0.6667


def test_candidate_no_assessments():
    """Test candidate with CV matching but no assessments done."""
    combined_data = {
        "skills": [
            {
                "skill": "FastAPI",
                "required_level": "intermediate",
                "importance": "required",
                "matched": True,
                "assessed_level": None,
                "ml_predicted_level": None,
                "level_gap": None
            }
        ],
        "score_data": {"score": 100.0}
    }
    feats = build_overall_features(combined_data)

    assert feats["total_skill_count"] == 1.0
    assert feats["required_skill_count"] == 1.0
    assert feats["preferred_skill_count"] == 0.0
    assert feats["cv_match_ratio"] == 1.0
    assert feats["assessed_skills_ratio"] == 0.0
    assert feats["required_assessment_coverage"] == 0.0
    assert feats["avg_assessment_score"] == 0.0
    assert feats["avg_level_gap"] == 0.0
    assert feats["max_level_gap"] == 0.0
    assert feats["zero_gap_skills_ratio"] == 0.0
    assert feats["ml_meets_req_ratio"] == 0.0


def test_candidate_missing_skills():
    """Test candidate with missing skills."""
    combined_data = {
        "matched_skills": [
            {
                "skill": "Python",
                "required_level": "advanced",
                "importance": "required",
                "matched": True,
                "assessed_level": "advanced",
                "ml_predicted_level": "advanced",
                "level_gap": 0,
                "total_score": 0.95
            }
        ],
        "missing_skills": [
            {
                "skill": "Kubernetes",
                "required_level": "intermediate",
                "importance": "required",
                "matched": False,
                "assessed_level": None,
                "ml_predicted_level": None,
                "level_gap": None
            }
        ],
        "score_data": {"score": 50.0}
    }

    feats = build_overall_features(combined_data)

    assert feats["total_skill_count"] == 2.0
    assert feats["required_skill_count"] == 2.0
    assert feats["preferred_skill_count"] == 0.0
    assert feats["cv_match_ratio"] == 0.5
    assert feats["required_skills_match_ratio"] == 0.5
    assert feats["required_assessment_coverage"] == 0.5  # 1 of 2 required assessed


def test_candidate_assessed_level_exceeds_required():
    """Test candidate whose assessed level exceeds required level (level gap is 0)."""
    combined_data = {
        "skills": [
            {
                "skill": "Python",
                "required_level": "basic",
                "importance": "required",
                "matched": True,
                "assessed_level": "advanced",
                "ml_predicted_level": "advanced",
                "level_gap": 0,
                "total_score": 0.98
            }
        ],
        "score_data": {"score": 100.0}
    }

    feats = build_overall_features(combined_data)

    assert feats["avg_level_gap"] == 0.0
    assert feats["max_level_gap"] == 0.0
    assert feats["zero_gap_skills_ratio"] == 1.0
    assert feats["ml_meets_req_ratio"] == 1.0  # advanced (3) >= basic (1)


def test_candidate_with_level_gaps():
    """Test candidate with level gaps."""
    combined_data = {
        "skills": [
            {
                "skill": "Python",
                "required_level": "advanced",
                "importance": "required",
                "matched": True,
                "assessed_level": "basic",
                "ml_predicted_level": "basic",
                "level_gap": 2,  # advanced (3) - basic (1) = 2
                "total_score": 0.40
            },
            {
                "skill": "SQL",
                "required_level": "intermediate",
                "importance": "required",
                "matched": True,
                "assessed_level": "basic",
                "ml_predicted_level": "basic",
                "level_gap": 1,  # intermediate (2) - basic (1) = 1
                "total_score": 0.50
            }
        ],
        "score_data": {"score": 100.0}
    }

    feats = build_overall_features(combined_data)

    assert feats["avg_level_gap"] == 1.5  # (2 + 1) / 2
    assert feats["max_level_gap"] == 2.0
    assert feats["zero_gap_skills_ratio"] == 0.0
    assert feats["ml_meets_req_ratio"] == 0.0  # basic < advanced and basic < intermediate


def test_empty_skill_list():
    """Test input with an empty skill list."""
    combined_data = {
        "skills": [],
        "score_data": {"score": 0.0}
    }

    feats = build_overall_features(combined_data)

    assert feats["total_skill_count"] == 0.0
    assert feats["required_skill_count"] == 0.0
    assert feats["preferred_skill_count"] == 0.0
    assert feats["cv_match_ratio"] == 0.0
    assert feats["required_skills_match_ratio"] == 0.0
    assert feats["preferred_skills_match_ratio"] == 0.0
    assert feats["assessed_skills_ratio"] == 0.0
    assert feats["required_assessment_coverage"] == 0.0
    assert feats["avg_assessment_score"] == 0.0
    assert feats["avg_level_gap"] == 0.0
    assert feats["max_level_gap"] == 0.0
    assert feats["zero_gap_skills_ratio"] == 0.0
    assert feats["ml_meets_req_ratio"] == 0.0
    assert feats["cv_matching_score"] == 0.0


def test_required_preferred_ratios_and_coverage():
    """Test correct required/preferred counts, ratios, and required assessment coverage."""
    combined_data = {
        "skills": [
            {"skill": "A", "required_level": "basic", "importance": "required", "matched": True, "assessed_level": "basic"},
            {"skill": "B", "required_level": "basic", "importance": "required", "matched": False, "assessed_level": None},
            {"skill": "C", "required_level": "basic", "importance": "preferred", "matched": True, "assessed_level": "basic"},
            {"skill": "D", "required_level": "basic", "importance": "preferred", "matched": True, "assessed_level": None},
        ],
        "score_data": {"score": 75.0}
    }

    feats = build_overall_features(combined_data)

    assert feats["total_skill_count"] == 4.0
    assert feats["required_skill_count"] == 2.0
    assert feats["preferred_skill_count"] == 2.0
    assert feats["cv_match_ratio"] == 0.75
    assert feats["required_skills_match_ratio"] == 0.5  # 1 of 2 required matched
    assert feats["preferred_skills_match_ratio"] == 1.0  # 2 of 2 preferred matched
    assert feats["assessed_skills_ratio"] == 0.5  # 2 of 4 total assessed
    assert feats["required_assessment_coverage"] == 0.5  # 1 of 2 required assessed


def test_ml_predicted_level_comparison():
    """Test correct ML predicted level numerical comparison against required level."""
    combined_data = {
        "skills": [
            # Case 1: ml_predicted basic (1) < intermediate (2) -> False
            {"skill": "A", "required_level": "intermediate", "ml_predicted_level": "basic"},
            # Case 2: ml_predicted intermediate (2) == intermediate (2) -> True
            {"skill": "B", "required_level": "intermediate", "ml_predicted_level": "intermediate"},
            # Case 3: ml_predicted advanced (3) > intermediate (2) -> True
            {"skill": "C", "required_level": "intermediate", "ml_predicted_level": "advanced"},
        ]
    }

    feats = build_overall_features(combined_data)

    assert pytest.approx(feats["ml_meets_req_ratio"], abs=1e-3) == 0.6667  # 2 of 3 meet requirement


def test_division_by_zero_safety():
    """Test division-by-zero safety across empty inputs or invalid types."""
    feats1 = build_overall_features({})
    assert feats1["total_skill_count"] == 0.0
    assert feats1["required_skill_count"] == 0.0
    assert feats1["preferred_skill_count"] == 0.0
    assert feats1["required_assessment_coverage"] == 0.0

    with pytest.raises(ValueError, match="Input must be a dictionary"):
        build_overall_features("not a dict")
