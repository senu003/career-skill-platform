import unittest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import AssessmentQuestion, QuestionOption, AssessmentAttempt, AssessmentAnswer
from app.services import assessment_service
from app.ml.predict_weakness import Model1SkillEvaluator, predict_skill_evaluator
from app.services.skill_analysis_service import combine_cv_and_assessment, get_assessment_result_for_skill


class TestModel1QuestionBankAndTelemetry(unittest.TestCase):

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        TestingSessionLocal = sessionmaker(bind=self.engine)
        self.db = TestingSessionLocal()
        self._seed_bank()

    def tearDown(self):
        self.db.close()

    def _seed_bank(self):
        # Seed 8 basic questions for JavaScript
        for i in range(1, 9):
            q = AssessmentQuestion(
                id=i,
                skill="JavaScript",
                level="basic",
                topic="Basics",
                question=f"Test Question {i}?",
                correct_answer="A",
                question_type="MCQ",
                is_active=True
            )
            self.db.add(q)
            self.db.flush()
            for opt in ["A", "B", "C", "D"]:
                self.db.add(QuestionOption(question_id=q.id, option_key=opt, option_text=f"Opt {opt}"))
        self.db.commit()

    # 1. QUESTION BANK & SELECTION TESTS
    def test_random_question_selection_limit(self):
        """Questions are selected from the bank up to requested limit."""
        questions = assessment_service.fetch_questions_for_level(self.db, "JavaScript", "basic", limit=5)
        self.assertEqual(len(questions), 5)
        valid_ids = list(range(1, 9))
        for q in questions:
            self.assertIn(q["id"], valid_ids)
            self.assertEqual(q["question_type"], "MCQ")
            self.assertNotIn("correct_answer", q)

    def test_unseen_questions_preferred(self):
        """Candidate prefers unseen questions over previously answered questions."""
        user_id = 42
        # Candidate has answered questions 1, 2, 3 in past attempt
        attempt = AssessmentAttempt(id=1, user_id=user_id, skill="JavaScript", required_level="basic")
        self.db.add(attempt)
        self.db.commit()

        for q_id in [1, 2, 3]:
            ans = AssessmentAnswer(attempt_id=1, question_id=q_id, selected_answer="A", is_correct=True)
            self.db.add(ans)
        self.db.commit()

        # Fetch 5 questions for user_id=42
        questions = assessment_service.fetch_questions_for_level(self.db, "JavaScript", "basic", user_id=user_id, limit=5)
        self.assertEqual(len(questions), 5)
        selected_ids = [q["id"] for q in questions]

        # 4, 5, 6, 7, 8 are unseen (5 total), so all selected IDs must be from unseen questions!
        for unseen_id in [4, 5, 6, 7, 8]:
            self.assertIn(unseen_id, selected_ids)

    def test_small_question_bank_fallback(self):
        """Fallback to seen questions when unseen questions are fewer than requested limit."""
        user_id = 99
        attempt = AssessmentAttempt(id=2, user_id=user_id, skill="JavaScript", required_level="basic")
        self.db.add(attempt)
        self.db.commit()

        # Mark 6 of 8 questions as seen
        for q_id in [1, 2, 3, 4, 5, 6]:
            self.db.add(AssessmentAnswer(attempt_id=2, question_id=q_id, selected_answer="A", is_correct=True))
        self.db.commit()

        # Fetch 5 questions for user_id=99 (only 2 unseen exist: 7 and 8)
        questions = assessment_service.fetch_questions_for_level(self.db, "JavaScript", "basic", user_id=user_id, limit=5)
        self.assertEqual(len(questions), 5)
        selected_ids = [q["id"] for q in questions]
        self.assertIn(7, selected_ids)
        self.assertIn(8, selected_ids)

    def test_telemetry_time_taken_saved(self):
        """time_taken telemetry is stored accurately in AssessmentAnswer."""
        attempt_res = assessment_service.start_assessment(self.db, "JavaScript", "basic", user_id=10)
        attempt_id = attempt_res["attempt_id"]
        q1_id = attempt_res["questions"][0]["id"]

        ans_res = assessment_service.submit_answer(
            db=self.db,
            attempt_id=attempt_id,
            question_id=q1_id,
            selected_answer="A",
            time_taken=14.5
        )
        self.assertTrue(ans_res["is_correct"])

        db_ans = self.db.query(AssessmentAnswer).filter(
            AssessmentAnswer.attempt_id == attempt_id,
            AssessmentAnswer.question_id == q1_id
        ).first()
        self.assertIsNotNone(db_ans)
        self.assertEqual(float(db_ans.time_taken), 14.5)

    # 2. FEATURE ENGINEERING TESTS
    def test_feature_engineering_defaults_and_fallbacks(self):
        """Tests robust feature calculation when timing, CV level, or scores are missing."""
        incomplete_input = {
            "required_level": "intermediate",
            "basic_score": 0.8,
            "intermediate_score": 0.6
        }
        feats = Model1SkillEvaluator.prepare_features(incomplete_input)
        self.assertEqual(feats["jd_required_level"], 2.0)
        self.assertEqual(feats["cv_parsed_level"], 0.0)  # Missing CV level -> 0
        self.assertEqual(feats["avg_time_per_question"], 30.0)  # Fallback -> 30.0
        self.assertEqual(feats["relative_time"], 1.0)
        self.assertEqual(feats["attempt_count"], 1.0)
        self.assertGreater(feats["speed_accuracy"], 0.0)

    # 3. MODEL PREDICTION SCENARIOS
    def test_model_prediction_scenarios(self):
        """Tests Model 1 predictions across candidate performance profiles."""
        # Strong candidate -> Mastered
        res_strong = predict_skill_evaluator({
            "jd_required_level": 2,
            "cv_parsed_level": 2,
            "basic_score": 1.0,
            "intermediate_score": 0.9,
            "advanced_score": 0.8,
            "assessment_score": 0.92,
            "avg_time_per_question": 22.0
        })
        self.assertIn(res_strong["recommendation"], ["Mastered", "Speed Practice"])
        self.assertGreaterEqual(res_strong["confidence"], 0.0)

        # High score + slow timing -> Speed Practice
        res_slow = predict_skill_evaluator({
            "jd_required_level": 2,
            "cv_parsed_level": 2,
            "basic_score": 0.95,
            "intermediate_score": 0.90,
            "advanced_score": 0.80,
            "assessment_score": 0.90,
            "avg_time_per_question": 65.0
        })
        self.assertEqual(res_slow["recommendation"], "Speed Practice")

        # Weak basic performance -> Re-learn Basics
        res_weak = predict_skill_evaluator({
            "jd_required_level": 2,
            "cv_parsed_level": 0,
            "basic_score": 0.30,
            "intermediate_score": 0.10,
            "advanced_score": 0.0,
            "assessment_score": 0.20,
            "avg_time_per_question": 45.0
        })
        self.assertEqual(res_weak["recommendation"], "Re-learn Basics")

    # 4. INTEGRATION TESTS
    def test_skill_analysis_integration_with_model1(self):
        """Verifies skill analysis retains existing contracts and includes Model 1 recommendations."""
        cv_match = {
            "filename": "resume.pdf",
            "pages": 1,
            "matched_skills": [
                {"skill": "JavaScript", "required_level": "intermediate", "importance": "required"}
            ],
            "missing_skills": [
                {"skill": "Docker", "required_level": "basic", "importance": "preferred"}
            ]
        }

        # Assessment mock data for JavaScript
        mock_assessments = {
            "JavaScript": {
                "assessed_level": "intermediate",
                "basic_score": 1.0,
                "intermediate_score": 0.8,
                "advanced_score": 0.6,
                "total_score": 0.82
            }
        }

        combined = combine_cv_and_assessment(cv_match, db_or_assessments=mock_assessments)
        self.assertEqual(len(combined["matched_skills"]), 1)
        js_skill = combined["matched_skills"][0]
        self.assertEqual(js_skill["skill"], "JavaScript")
        self.assertEqual(js_skill["assessed_level"], "intermediate")
        self.assertIsNotNone(js_skill["skill_recommendation"])
        self.assertIsNotNone(js_skill["recommendation_confidence"])

        # Missing skill (Docker) has no assessment -> null assessed_level & skill_recommendation
        docker_skill = combined["missing_skills"][0]
        self.assertEqual(docker_skill["skill"], "Docker")
        self.assertIsNone(docker_skill["assessed_level"])
        self.assertIsNone(docker_skill["skill_recommendation"])


if __name__ == "__main__":
    unittest.main()
