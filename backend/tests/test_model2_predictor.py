"""
TESTS FOR MODEL 2 PREDICTOR & DETERMINISTIC SAFETY LAYER
"""

import unittest
from app.ml.predict_readiness import Model2FinalRecommendationPredictor, predict_final_recommendation


class TestModel2Predictor(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.predictor = Model2FinalRecommendationPredictor()

    def test_scenario_a_strong_candidate(self):
        """
        Scenario A — Strong candidate:
        few/no missing skills, small average gap, high assessment accuracy, few/no upgrades
        Expected: Interview Ready
        """
        input_data = {
            "matched_skills": [
                {"skill": "Python", "required_level": "advanced", "importance": "required", "matched": True, "assessed_level": "advanced", "level_gap": 0, "total_score": 0.95, "skill_recommendation": "Mastered"},
                {"skill": "FastAPI", "required_level": "intermediate", "importance": "required", "matched": True, "assessed_level": "intermediate", "level_gap": 0, "total_score": 0.90, "skill_recommendation": "Mastered"},
                {"skill": "PostgreSQL", "required_level": "basic", "importance": "required", "matched": True, "assessed_level": "basic", "level_gap": 0, "total_score": 0.85, "skill_recommendation": "Speed Practice"}
            ],
            "missing_skills": []
        }

        res = self.predictor.predict(input_data)
        self.assertEqual(res["final_verdict"], "Interview Ready")
        self.assertGreaterEqual(res["confidence"], 0.50)

    def test_scenario_b_moderate_gaps(self):
        """
        Scenario B — Small/moderate gaps:
        1–2 important gaps, moderate assessment score, some Upgrade Needed skills
        Expected: Short-Term Prep
        """
        input_data = {
            "matched_skills": [
                {"skill": "Python", "required_level": "advanced", "importance": "required", "matched": True, "assessed_level": "intermediate", "level_gap": 1, "total_score": 0.65, "skill_recommendation": "Upgrade Needed"},
                {"skill": "SQL", "required_level": "intermediate", "importance": "required", "matched": True, "assessed_level": "basic", "level_gap": 1, "total_score": 0.60, "skill_recommendation": "Upgrade Needed"}
            ],
            "missing_skills": [
                {"skill": "Docker", "required_level": "intermediate", "importance": "preferred", "matched": False, "level_gap": 2, "skill_recommendation": "Upgrade Needed"}
            ]
        }

        res = self.predictor.predict(input_data)
        self.assertEqual(res["final_verdict"], "Short-Term Prep")

    def test_scenario_c_major_gaps(self):
        """
        Scenario C — Major gaps:
        many missing skills, large average gap, low assessment accuracy, many Upgrade Needed / Re-learn Basics skills
        Expected: Major Upskill Required
        """
        input_data = {
            "matched_skills": [
                {"skill": "Git", "required_level": "basic", "importance": "required", "matched": True, "assessed_level": "basic", "level_gap": 0, "total_score": 0.40, "skill_recommendation": "Re-learn Basics"}
            ],
            "missing_skills": [
                {"skill": "Python", "required_level": "advanced", "importance": "required", "matched": False, "level_gap": 3, "skill_recommendation": "Re-learn Basics"},
                {"skill": "PostgreSQL", "required_level": "advanced", "importance": "required", "matched": False, "level_gap": 3, "skill_recommendation": "Upgrade Needed"},
                {"skill": "React", "required_level": "intermediate", "importance": "required", "matched": False, "level_gap": 2, "skill_recommendation": "Upgrade Needed"}
            ]
        }

        res = self.predictor.predict(input_data)
        self.assertEqual(res["final_verdict"], "Major Upskill Required")

    def test_safety_layer_overrides_nonsensical_ready_on_missing_skills(self):
        """
        Candidate missing almost all skills must not be classified as Interview Ready.
        """
        features = {
            "total_required_skills": 5.0,
            "missing_skills_count": 4.0,  # 80% missing
            "average_skill_gap": 2.5,
            "overall_assessment_accuracy": 0.90,
            "upgrade_needed_count": 0.0,
            "mastered_count": 1.0,
            "speed_practice_count": 0.0,
            "relearn_basics_count": 0.0,
            "assessed_skills_count": 1.0,
            "assessment_completion_rate": 0.20
        }

        raw_verdict = "Interview Ready"
        adjusted_verdict, conf = self.predictor._apply_safety_layer(raw_verdict, 0.85, features)
        self.assertEqual(adjusted_verdict, "Major Upskill Required")

    def test_convenience_function(self):
        analysis = {
            "matched_skills": [
                {"skill": "Python", "required_level": "advanced", "importance": "required", "matched": True, "assessed_level": "advanced", "level_gap": 0, "total_score": 0.95, "skill_recommendation": "Mastered"}
            ],
            "missing_skills": []
        }
        res = predict_final_recommendation(analysis)
        self.assertIn(res["final_verdict"], ["Interview Ready", "Short-Term Prep", "Major Upskill Required"])
        self.assertIn("confidence", res)
        self.assertIn("priority_skills", res)


if __name__ == "__main__":
    unittest.main()
