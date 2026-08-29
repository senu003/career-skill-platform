import sys
import os
import unittest

# Ensure backend package is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.scoring_service import calculate_skill_score


class TestScoringService(unittest.TestCase):

    def test_calculate_skill_score_normal(self):
        matched_skills = [
            {"skill": "Python", "level": "advanced", "importance": "required"},
            {"skill": "FastAPI", "level": "intermediate", "importance": "required"},
            {"skill": "Docker", "level": "basic", "importance": "preferred"}
        ]
        missing_skills = [
            {"skill": "Kubernetes", "level": "intermediate", "importance": "required"}
        ]

        result = calculate_skill_score(matched_skills, missing_skills)

        self.assertEqual(result["total_skills"], 4)
        self.assertEqual(result["matched_count"], 3)
        self.assertEqual(result["missing_count"], 1)
        self.assertEqual(result["score"], 75.0)

    def test_calculate_skill_score_100_percent(self):
        matched_skills = [
            {"skill": "Python", "level": "advanced", "importance": "required"}
        ]
        missing_skills = []

        result = calculate_skill_score(matched_skills, missing_skills)

        self.assertEqual(result["total_skills"], 1)
        self.assertEqual(result["matched_count"], 1)
        self.assertEqual(result["missing_count"], 0)
        self.assertEqual(result["score"], 100.0)

    def test_calculate_skill_score_zero_percent(self):
        matched_skills = []
        missing_skills = [
            {"skill": "Python", "level": "advanced", "importance": "required"},
            {"skill": "Java", "level": "intermediate", "importance": "required"}
        ]

        result = calculate_skill_score(matched_skills, missing_skills)

        self.assertEqual(result["total_skills"], 2)
        self.assertEqual(result["matched_count"], 0)
        self.assertEqual(result["missing_count"], 2)
        self.assertEqual(result["score"], 0.0)

    def test_calculate_skill_score_empty_lists(self):
        result = calculate_skill_score([], [])

        self.assertEqual(result["total_skills"], 0)
        self.assertEqual(result["matched_count"], 0)
        self.assertEqual(result["missing_count"], 0)
        self.assertEqual(result["score"], 0.0)

    def test_calculate_skill_score_none_inputs(self):
        result = calculate_skill_score(None, None)

        self.assertEqual(result["total_skills"], 0)
        self.assertEqual(result["matched_count"], 0)
        self.assertEqual(result["missing_count"], 0)
        self.assertEqual(result["score"], 0.0)

    def test_calculate_skill_score_rounding(self):
        matched_skills = [{"skill": "Python"}, {"skill": "FastAPI"}]
        missing_skills = [{"skill": "Docker"}]

        result = calculate_skill_score(matched_skills, missing_skills)

        self.assertEqual(result["total_skills"], 3)
        self.assertEqual(result["matched_count"], 2)
        self.assertEqual(result["missing_count"], 1)
        self.assertEqual(result["score"], 66.67)


if __name__ == "__main__":
    unittest.main()
