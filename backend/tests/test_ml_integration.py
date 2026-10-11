import os
import sys
import unittest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import SessionLocal
from app.models import AssessmentAttempt, AssessmentAnswer, AssessmentQuestion
from app.ml.predict import SkillLevelPredictor, DEFAULT_MODEL_PATH
from app.services.skill_analysis_service import combine_cv_and_assessment


class TestMLIntegration(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_01_ml_predictor_loads_saved_model(self):
        """1. ML predictor loads the saved model file."""
        self.assertTrue(DEFAULT_MODEL_PATH.exists(), f"Model file missing at {DEFAULT_MODEL_PATH}")
        predictor = SkillLevelPredictor(model_path=DEFAULT_MODEL_PATH)
        self.assertIsNotNone(predictor.pipeline)

    def test_02_valid_feature_input_produces_prediction(self):
        """2. Valid feature input produces a valid prediction structure."""
        predictor = SkillLevelPredictor()
        features = {
            "cv_matched": True,
            "required_level": "intermediate",
            "importance": "required",
            "basic_score": 0.9,
            "intermediate_score": 0.8,
            "advanced_score": 0.4,
            "total_score": 0.72
        }
        res = predictor.predict_single(features)
        self.assertIn("predicted_level", res)
        self.assertIn("probabilities", res)

    def test_03_prediction_is_one_of_valid_levels(self):
        """3. Prediction is strictly one of: basic, intermediate, or advanced."""
        predictor = SkillLevelPredictor()
        features = {
            "cv_matched": 1,
            "required_level": "advanced",
            "importance": "required",
            "basic_score": 1.0,
            "intermediate_score": 0.9,
            "advanced_score": 0.85,
            "total_score": 0.915
        }
        res = predictor.predict_single(features)
        valid_levels = {"basic", "intermediate", "advanced"}
        self.assertIn(res["predicted_level"], valid_levels)

    def test_04_invalid_score_values_rejected(self):
        """4. Invalid score values (> 1.0 or < 0.0) are rejected."""
        predictor = SkillLevelPredictor()
        invalid_features = {
            "cv_matched": True,
            "required_level": "intermediate",
            "importance": "required",
            "basic_score": 1.5,  # Out of bounds (> 1.0)
            "intermediate_score": 0.8,
            "advanced_score": 0.4,
            "total_score": 0.7
        }
        with self.assertRaises(ValueError):
            predictor.predict_single(invalid_features)

        # Test via POST /ml/predict endpoint
        res = self.client.post("/ml/predict", json=invalid_features)
        self.assertIn(res.status_code, [400, 422])

    def test_05_missing_required_feature_values_handled(self):
        """5. Missing required feature values are handled safely."""
        predictor = SkillLevelPredictor()
        incomplete_features = {
            "cv_matched": True,
            "required_level": "intermediate"
            # Missing score fields & importance
        }
        with self.assertRaises(ValueError):
            predictor.predict_single(incomplete_features)

        res = self.client.post("/ml/predict", json=incomplete_features)
        self.assertIn(res.status_code, [400, 422])

    def test_06_post_ml_predict_endpoint_works(self):
        """6. POST /ml/predict endpoint accepts valid JSON features and returns predicted_level."""
        payload = {
            "cv_matched": 1,
            "required_level": "advanced",
            "importance": "required",
            "basic_score": 1.0,
            "intermediate_score": 0.8,
            "advanced_score": 0.6,
            "total_score": 0.8
        }
        res = self.client.post("/ml/predict", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("predicted_level", data)
        self.assertIn(data["predicted_level"], ["basic", "intermediate", "advanced"])

    def test_09_assessed_level_never_overwritten_by_ml(self):
        """9. assessed_level is NEVER overwritten by ML prediction."""
        cv_result = {
            "matched_skills": [
                {"skill": "JavaScript", "level": "advanced", "importance": "required", "evidence": "JS code"}
            ],
            "missing_skills": []
        }
        assessments = {
            "JavaScript": {
                "assessed_level": "intermediate",  # Deterministic assessment level
                "basic_score": 1.0,
                "intermediate_score": 1.0,
                "advanced_score": 0.9,
                "total_score": 0.965
            }
        }
        combined = combine_cv_and_assessment(cv_result, db_or_assessments=assessments)
        item = combined["matched_skills"][0]

        # assessed_level must remain deterministic value
        self.assertEqual(item["assessed_level"], "intermediate")
        # ml_predicted_level is populated independently
        self.assertIsNotNone(item["ml_predicted_level"])
        self.assertIn(item["ml_predicted_level"], ["basic", "intermediate", "advanced"])

    def test_10_ml_predicted_level_can_differ_from_assessed_level(self):
        """10. ml_predicted_level can differ from assessed_level without causing errors."""
        cv_result = {
            "matched_skills": [
                {"skill": "JavaScript", "level": "advanced", "importance": "required", "evidence": "JS code"}
            ],
            "missing_skills": []
        }
        assessments = {
            "JavaScript": {
                "assessed_level": "intermediate",
                "basic_score": 1.0,
                "intermediate_score": 0.9,
                "advanced_score": 0.9,
                "total_score": 0.935
            }
        }
        combined = combine_cv_and_assessment(cv_result, db_or_assessments=assessments)
        item = combined["matched_skills"][0]

        # Verify assessed_level is intermediate while ml_predicted_level could be advanced/other
        self.assertEqual(item["assessed_level"], "intermediate")
        self.assertIsNotNone(item["ml_predicted_level"])
        # No exception raised, both values preserved

    def test_11_unavailable_assessment_data_returns_null_ml_predicted_level(self):
        """11. If assessment data is unavailable, ml_predicted_level is null rather than fabricated."""
        cv_result = {
            "matched_skills": [
                {"skill": "Python", "level": "intermediate", "importance": "required", "evidence": "Py code"}
            ],
            "missing_skills": [
                {"skill": "Docker", "level": "basic", "importance": "required"}
            ]
        }
        # No assessment data passed
        combined = combine_cv_and_assessment(cv_result, db_or_assessments={})

        matched_py = combined["matched_skills"][0]
        missing_docker = combined["missing_skills"][0]

        self.assertIsNone(matched_py["assessed_level"])
        self.assertIsNone(matched_py["ml_predicted_level"])

        self.assertIsNone(missing_docker["assessed_level"])
        self.assertIsNone(missing_docker["ml_predicted_level"])

    def test_12_model1_predict_single_fallback_when_pipeline_none(self):
        """12. Model 1 predict_single returns fallback if pipeline is None."""
        from app.ml.predict_weakness import Model1SkillEvaluator
        evaluator = Model1SkillEvaluator()
        evaluator.pipeline = None
        
        # Test 1: Upgrade Needed fallback (score_gap > 0)
        input_dict_gap = {
            "jd_required_level": "intermediate",
            "assessed_level": "basic",
            "assessment_score": 0.8
        }
        res_gap = evaluator.predict_single(input_dict_gap)
        self.assertEqual(res_gap["recommendation"], "Upgrade Needed")
        
        # Test 2: Mastered fallback (no gap, good score)
        input_dict_master = {
            "jd_required_level": "intermediate",
            "assessed_level": "advanced",
            "assessment_score": 0.9
        }
        res_master = evaluator.predict_single(input_dict_master)
        self.assertEqual(res_master["recommendation"], "Mastered")
        
    def test_13_model1_predict_single_fallback_on_exception(self):
        """13. Model 1 predict_single returns fallback if prediction raises an exception."""
        from app.ml.predict_weakness import Model1SkillEvaluator
        evaluator = Model1SkillEvaluator()
        
        # Mock pipeline to raise exception
        class BadPipeline:
            def predict(self, X):
                raise ValueError("Simulated prediction error")
        
        evaluator.pipeline = BadPipeline()
        input_dict = {
            "jd_required_level": "basic",
            "assessed_level": "basic",
            "assessment_score": 0.4  # < 0.60, so fallback should be Upgrade Needed
        }
        res = evaluator.predict_single(input_dict)
        self.assertEqual(res["recommendation"], "Upgrade Needed")

if __name__ == "__main__":
    unittest.main()
