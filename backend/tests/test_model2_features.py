"""
TESTS FOR MODEL 2 FEATURE EXTRACTION AND PRIORITY SKILL RANKING
"""

import unittest
from app.ml.readiness_features import (
    extract_model2_features,
    calculate_skill_priority_score,
    compute_priority_skills
)


class TestModel2Features(unittest.TestCase):

    def test_feature_aggregation_complete(self):
        sample_analysis = {
            "matched_skills": [
                {
                    "skill": "Python",
                    "required_level": "advanced",
                    "importance": "required",
                    "matched": True,
                    "assessed_level": "advanced",
                    "level_gap": 0,
                    "total_score": 0.92,
                    "skill_recommendation": "Mastered",
                    "recommendation_confidence": 0.88
                },
                {
                    "skill": "FastAPI",
                    "required_level": "intermediate",
                    "importance": "required",
                    "matched": True,
                    "assessed_level": "basic",
                    "level_gap": 1,
                    "total_score": 0.60,
                    "skill_recommendation": "Upgrade Needed",
                    "recommendation_confidence": 0.82
                }
            ],
            "missing_skills": [
                {
                    "skill": "Docker",
                    "required_level": "intermediate",
                    "importance": "preferred",
                    "matched": False,
                    "assessed_level": None,
                    "level_gap": 2,
                    "total_score": None,
                    "skill_recommendation": "Upgrade Needed",
                    "recommendation_confidence": 0.75
                }
            ]
        }

        feats = extract_model2_features(sample_analysis)

        self.assertEqual(feats["total_required_skills"], 3.0)
        self.assertEqual(feats["missing_skills_count"], 1.0)
        self.assertAlmostEqual(feats["average_skill_gap"], 1.0, places=2)  # (0 + 1 + 2) / 3 = 1.0
        self.assertAlmostEqual(feats["overall_assessment_accuracy"], 0.76, places=2)  # (0.92 + 0.60) / 2 = 0.76
        self.assertEqual(feats["upgrade_needed_count"], 2.0)
        self.assertEqual(feats["mastered_count"], 1.0)
        self.assertEqual(feats["speed_practice_count"], 0.0)
        self.assertEqual(feats["relearn_basics_count"], 0.0)
        self.assertEqual(feats["assessed_skills_count"], 3.0)
        self.assertAlmostEqual(feats["assessment_completion_rate"], 1.0, places=2)

    def test_feature_aggregation_missing_unassessed_data(self):
        sample_analysis = {
            "matched_skills": [
                {
                    "skill": "Python",
                    "required_level": "basic",
                    "importance": "required",
                    "matched": True
                }
            ],
            "missing_skills": []
        }

        feats = extract_model2_features(sample_analysis)
        self.assertEqual(feats["total_required_skills"], 1.0)
        self.assertEqual(feats["missing_skills_count"], 0.0)
        self.assertEqual(feats["average_skill_gap"], 0.0)
        self.assertEqual(feats["overall_assessment_accuracy"], 0.0)
        self.assertEqual(feats["assessed_skills_count"], 0.0)
        self.assertEqual(feats["assessment_completion_rate"], 0.0)

    def test_priority_ranking_larger_gap_higher_priority(self):
        skill_small_gap = {
            "skill": "SQL",
            "required_level": "advanced",
            "importance": "required",
            "matched": True,
            "level_gap": 1,
            "skill_recommendation": "Speed Practice"
        }
        skill_large_gap = {
            "skill": "Docker",
            "required_level": "advanced",
            "importance": "required",
            "matched": True,
            "level_gap": 3,
            "skill_recommendation": "Re-learn Basics"
        }

        score_small = calculate_skill_priority_score(skill_small_gap)["priority_score"]
        score_large = calculate_skill_priority_score(skill_large_gap)["priority_score"]

        self.assertGreater(score_large, score_small)

    def test_priority_ranking_higher_importance_increases_priority(self):
        skill_preferred = {
            "skill": "Docker",
            "required_level": "intermediate",
            "importance": "preferred",
            "matched": True,
            "level_gap": 2,
            "skill_recommendation": "Upgrade Needed"
        }
        skill_required = {
            "skill": "Docker",
            "required_level": "intermediate",
            "importance": "required",
            "matched": True,
            "level_gap": 2,
            "skill_recommendation": "Upgrade Needed"
        }

        score_pref = calculate_skill_priority_score(skill_preferred)["priority_score"]
        score_req = calculate_skill_priority_score(skill_required)["priority_score"]

        self.assertGreater(score_req, score_pref)

    def test_priority_ranking_mastered_lower_than_weak(self):
        skill_mastered = {
            "skill": "Python",
            "required_level": "advanced",
            "importance": "required",
            "matched": True,
            "level_gap": 0,
            "skill_recommendation": "Mastered"
        }
        skill_weak = {
            "skill": "React",
            "required_level": "intermediate",
            "importance": "required",
            "matched": True,
            "level_gap": 1,
            "skill_recommendation": "Upgrade Needed"
        }

        score_mastered = calculate_skill_priority_score(skill_mastered)["priority_score"]
        score_weak = calculate_skill_priority_score(skill_weak)["priority_score"]

        self.assertGreater(score_weak, score_mastered)

    def test_priority_skills_deterministic_and_sorted(self):
        skills = [
            {"skill": "A", "required_level": "basic", "importance": "required", "skill_recommendation": "Mastered", "level_gap": 0},
            {"skill": "B", "required_level": "advanced", "importance": "required", "skill_recommendation": "Re-learn Basics", "level_gap": 3},
            {"skill": "C", "required_level": "intermediate", "importance": "required", "skill_recommendation": "Upgrade Needed", "level_gap": 1}
        ]

        priority_list = compute_priority_skills(skills, top_n=3)
        self.assertEqual(len(priority_list), 3)
        self.assertEqual(priority_list[0]["skill"], "B")
        self.assertEqual(priority_list[1]["skill"], "C")
        self.assertEqual(priority_list[2]["skill"], "A")


if __name__ == "__main__":
    unittest.main()
