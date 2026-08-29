import os
import sys
import unittest
from typing import Dict, Any

# Ensure backend package directory is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models import AssessmentAttempt, AssessmentAnswer
from app.services.skill_analysis_service import extract_assessment_scores
from app.ml.predict import SkillLevelPredictor


class TestMLRealAssessmentTrace(unittest.TestCase):
    """
    Focused test/debug script to trace a real PostgreSQL assessment attempt (attempt_id=21)
    through the ML prediction pipeline and inspect feature extraction and model prediction output.
    """

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_trace_assessment_attempt_21(self):
        print("\n" + "=" * 70)
        print("REAL ASSESSMENT ML PREDICTION TRACE (attempt_id=21)")
        print("=" * 70)

        # ---------------------------------------------------------------------
        # 1. Load AssessmentAttempt and AssessmentAnswer records for attempt_id=21
        # ---------------------------------------------------------------------
        attempt_id = 21
        attempt = self.db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
        self.assertIsNotNone(attempt, f"AssessmentAttempt with id={attempt_id} not found in database.")

        answers = self.db.query(AssessmentAnswer).filter(AssessmentAnswer.attempt_id == attempt_id).all()
        self.assertGreater(len(answers), 0, f"No AssessmentAnswer records found for attempt_id={attempt_id}.")

        print(f"\n[STEP 1] Loaded DB Records for Attempt ID: {attempt_id}")
        print(f"  - Skill:                {attempt.skill}")
        print(f"  - User ID:              {attempt.user_id}")
        print(f"  - Required Level:       {attempt.required_level}")
        print(f"  - Assessed Level (DB):  {attempt.assessed_level}")
        print(f"  - Total Answer Count:   {len(answers)}")

        # ---------------------------------------------------------------------
        # 2. Extract scores using existing extract_assessment_scores()
        # ---------------------------------------------------------------------
        assessment_data = {"attempt_id": attempt_id}
        scores = extract_assessment_scores(self.db, assessment_data)
        self.assertIsNotNone(scores, "extract_assessment_scores returned None.")

        # ---------------------------------------------------------------------
        # 3. Print resulting scores
        # ---------------------------------------------------------------------
        print("\n[STEP 2 & 3] Extracted Assessment Scores (extract_assessment_scores):")
        print(f"  - basic_score:        {scores['basic_score']:.4f}")
        print(f"  - intermediate_score: {scores['intermediate_score']:.4f}")
        print(f"  - advanced_score:     {scores['advanced_score']:.4f}")
        print(f"  - total_score:        {scores['total_score']:.4f}")

        # ---------------------------------------------------------------------
        # 4. Construct & Print complete feature dictionary for SkillLevelPredictor
        # ---------------------------------------------------------------------
        feature_dict: Dict[str, Any] = {
            "cv_matched": 1,
            "required_level": attempt.required_level.lower().strip(),
            "importance": "required",
            "basic_score": scores["basic_score"],
            "intermediate_score": scores["intermediate_score"],
            "advanced_score": scores["advanced_score"],
            "total_score": scores["total_score"]
        }

        print("\n[STEP 4] Complete Feature Dictionary for SkillLevelPredictor:")
        for k, v in feature_dict.items():
            print(f"  - {k:<20}: {v}")

        # Validate feature dictionary schema
        validated_features = SkillLevelPredictor.validate_feature_dict(feature_dict)
        self.assertEqual(len(validated_features), 7)

        # ---------------------------------------------------------------------
        # 5. Call existing ML predictor
        # ---------------------------------------------------------------------
        predictor = SkillLevelPredictor()
        prediction_result = predictor.predict_single(feature_dict)

        # ---------------------------------------------------------------------
        # 6 & 7. Print ml_predicted_level and deterministic assessed_level
        # ---------------------------------------------------------------------
        ml_predicted_level = prediction_result["predicted_level"]
        probabilities = prediction_result.get("probabilities", {})
        assessed_level = attempt.assessed_level

        print("\n[STEP 5, 6 & 7] Model Prediction & Deterministic Assessment Output:")
        print(f"  - Deterministic Assessed Level (Rule-based) : {assessed_level}")
        print(f"  - ML Predicted Skill Level (Model-based)   : {ml_predicted_level}")
        print("  - Prediction Probabilities:")
        for cls_name, prob in probabilities.items():
            print(f"      * {cls_name:<12}: {prob:.4f} ({prob * 100:.2f}%)")

        # ---------------------------------------------------------------------
        # 8. Clearly show difference between Assessment Result and ML Prediction
        # ---------------------------------------------------------------------
        print("\n[STEP 8] Comparison & Pipeline Trace Analysis:")
        print("-" * 65)
        print(f"{'Metric / Pipeline Stage':<35} | {'Value'}")
        print("-" * 65)
        print(f"{'Target Skill':<35} | {attempt.skill}")
        print(f"{'Required Level':<35} | {attempt.required_level}")
        print(f"{'Total Questions Answered':<35} | {len(answers)}")
        print(f"{'Basic Level Score':<35} | {scores['basic_score']:.4f}")
        print(f"{'Intermediate Level Score':<35} | {scores['intermediate_score']:.4f}")
        print(f"{'Advanced Level Score':<35} | {scores['advanced_score']:.4f}")
        print(f"{'Weighted Total Score':<35} | {scores['total_score']:.4f}")
        print("-" * 65)
        print(f"{'Deterministic Assessment Result':<35} | {assessed_level}")
        print(f"{'ML Model Prediction':<35} | {ml_predicted_level}")

        is_match = (assessed_level == ml_predicted_level)
        print(f"{'Result Match Status':<35} | {'MATCH' if is_match else 'DIFFERENT'}")
        print("-" * 65)

        if is_match:
            print(f"\nConclusion: Both the rule-based assessment algorithm and the ML classifier agree that the candidate proficiency level is '{ml_predicted_level}'.")
        else:
            print(f"\nConclusion: The rule-based assessment evaluated the skill level as '{assessed_level}', whereas the ML classifier predicted '{ml_predicted_level}'.")

        # Basic assertions to ensure test validity
        self.assertIn(ml_predicted_level, ["basic", "intermediate", "advanced"])
        self.assertIn(assessed_level, ["basic", "intermediate", "advanced"])


if __name__ == "__main__":
    unittest.main()
