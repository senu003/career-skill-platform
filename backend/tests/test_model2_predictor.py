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
        self.assertEqual(res["final_verdict"], "Interview Ready")

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

        adjusted_verdict, conf = self.predictor._deterministic_verdict(features)
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

    def test_readiness_reasons_counts_required_skills_only(self):
        """Verify readiness_reasons counts required skills only when given 5 required + 1 preferred."""
        from app.ml.predict_readiness import generate_readiness_reasons

        # Direct test with 5 required + 1 preferred
        raw_skills = [
            {"skill": "Python", "required_level": "intermediate", "importance": "required", "matched": True, "cv_match_status": "Match"},
            {"skill": "SQL", "required_level": "intermediate", "importance": "required", "matched": True, "cv_match_status": "Match"},
            {"skill": "FastAPI", "required_level": "basic", "importance": "required", "matched": True, "cv_match_status": "Match"},
            {"skill": "Docker", "required_level": "basic", "importance": "required", "matched": False, "cv_match_status": "Missing"},
            {"skill": "Kubernetes", "required_level": "basic", "importance": "required", "matched": False, "cv_match_status": "Missing"},
            {"skill": "GraphQL", "required_level": "basic", "importance": "preferred", "matched": True, "cv_match_status": "Match"},
        ]
        features = {
            "total_required_skills": 6.0,
            "missing_skills_count": 2.0
        }
        reasons = generate_readiness_reasons("Short-Term Prep", features, raw_skills=raw_skills)
        self.assertGreaterEqual(len(reasons), 1)
        self.assertIn("3 of 5 required skills", reasons[0])
        self.assertNotIn("6 required skills", reasons[0])

        # Test through predict_final_recommendation pipeline
        analysis = {
            "matched_skills": [
                {"skill": "Python", "required_level": "intermediate", "importance": "required", "matched": True, "cv_match_status": "Match"},
                {"skill": "SQL", "required_level": "intermediate", "importance": "required", "matched": True, "cv_match_status": "Match"},
                {"skill": "FastAPI", "required_level": "basic", "importance": "required", "matched": True, "cv_match_status": "Match"},
                {"skill": "GraphQL", "required_level": "basic", "importance": "preferred", "matched": True, "cv_match_status": "Match"},
            ],
            "missing_skills": [
                {"skill": "Docker", "required_level": "basic", "importance": "required", "matched": False, "cv_match_status": "Missing"},
                {"skill": "Kubernetes", "required_level": "basic", "importance": "required", "matched": False, "cv_match_status": "Missing"},
            ]
        }
        pipeline_res = predict_final_recommendation(analysis)
        pipeline_reasons = pipeline_res.get("readiness_reasons", [])
        self.assertGreaterEqual(len(pipeline_reasons), 1)
        self.assertIn("3 of 5 required skills", pipeline_reasons[0])
        self.assertNotIn("6 required skills", pipeline_reasons[0])

    def test_zero_assessments_candidate_generates_preliminary_verdict(self):
        """
        Clarification 1: Candidates with 0 assessments must NOT be automatically classified
        as unready. Strong CV evidence should yield an appropriate preliminary verdict
        with explicit indication that technical proficiency has not been verified.
        """
        analysis = {
            "matched_skills": [
                {"skill": "Python", "required_level": "intermediate", "importance": "required", "matched": True, "cv_match_status": "Match"},
                {"skill": "SQL", "required_level": "basic", "importance": "required", "matched": True, "cv_match_status": "Match"},
                {"skill": "FastAPI", "required_level": "basic", "importance": "required", "matched": True, "cv_match_status": "Match"},
            ],
            "missing_skills": []
        }
        res = predict_final_recommendation(analysis)
        self.assertEqual(res["final_verdict"], "Interview Ready")
        self.assertTrue(res["is_preliminary"])
        self.assertEqual(res["verification_status"], "Unverified (Preliminary CV Evidence)")
        self.assertGreaterEqual(len(res["readiness_reasons"]), 1)
        self.assertIn("technical proficiency has not yet been verified", res["readiness_reasons"][0])

    def test_missing_cv_skill_not_treated_as_confirmed_failure(self):
        """
        Clarification 2: Skills missing from CV are 'Unverified / Not Mentioned'
        rather than confirmed failures. They should prompt assessment verification
        without triggering automatic unready classification.
        """
        analysis = {
            "matched_skills": [
                {"skill": "Python", "required_level": "intermediate", "importance": "required", "matched": True, "cv_match_status": "Match", "assessed_level": "intermediate", "level_gap": 0, "total_score": 0.90},
                {"skill": "FastAPI", "required_level": "basic", "importance": "required", "matched": True, "cv_match_status": "Match"},
            ],
            "missing_skills": [
                {"skill": "Docker", "required_level": "basic", "importance": "required", "matched": False, "cv_match_status": "Missing"}
            ]
        }
        res = predict_final_recommendation(analysis)
        # Missing Docker is unverified, not a hard failure; candidate passed Python and matched FastAPI
        self.assertIn(res["final_verdict"], ["Interview Ready", "Short-Term Prep"])
        reasons_text = " ".join(res.get("readiness_reasons", []))
        self.assertIn("Docker", reasons_text)
        self.assertIn("not mentioned in CV", reasons_text)


if __name__ == "__main__":
    unittest.main()

