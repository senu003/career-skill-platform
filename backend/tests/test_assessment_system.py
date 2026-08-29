import os
import sys
import unittest
from fastapi.testclient import TestClient

# Ensure backend package is in python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import SessionLocal
from app.models import AssessmentQuestion, AssessmentAttempt, AssessmentAnswer


class TestAssessmentSystem(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()

    def test_01_and_02_start_assessment_and_receive_questions(self):
        """1. Start JavaScript basic assessment & 2. Receive 5 basic questions."""
        response = self.client.post("/assessment/start", json={
            "skill": "JavaScript",
            "required_level": "basic",
            "user_id": 101
        })
        self.assertEqual(response.status_code, 201)
        data = response.json()

        self.assertIn("attempt_id", data)
        self.assertEqual(data["skill"], "JavaScript")
        self.assertEqual(data["required_level"], "basic")
        self.assertIsNone(data["cv_level"])
        self.assertEqual(data["current_level"], "basic")
        self.assertEqual(len(data["questions"]), 5)

        for q in data["questions"]:
            self.assertEqual(q["level"], "basic")
            self.assertIn("A", q["options"])
            self.assertIn("B", q["options"])
            self.assertIn("C", q["options"])
            self.assertIn("D", q["options"])
            # Requirement 10: Never return correct_answer
            self.assertNotIn("correct_answer", q)

    def test_03_04_05_submit_answers_and_db_storage(self):
        """3. Submit answers, 4. Verify correct/incorrect values, 5. Verify stored in DB."""
        # Start basic attempt
        start_res = self.client.post("/assessment/start", json={
            "skill": "JavaScript",
            "required_level": "basic"
        }).json()

        attempt_id = start_res["attempt_id"]
        questions = start_res["questions"]

        # Submit answer for first question
        q1 = questions[0]
        sub_res = self.client.post("/assessment/answer", json={
            "attempt_id": attempt_id,
            "question_id": q1["id"],
            "selected_answer": "C"  # correct answer for JS-B01
        })
        self.assertEqual(sub_res.status_code, 200)
        data = sub_res.json()

        self.assertEqual(data["attempt_id"], attempt_id)
        self.assertEqual(data["question_id"], q1["id"])
        self.assertEqual(data["selected_answer"], "C")
        self.assertTrue(data["is_correct"])

        # Check DB directly
        db_answer = self.db.query(AssessmentAnswer).filter(
            AssessmentAnswer.attempt_id == attempt_id,
            AssessmentAnswer.question_id == q1["id"]
        ).first()
        self.assertIsNotNone(db_answer)
        self.assertEqual(db_answer.selected_answer, "C")
        self.assertTrue(db_answer.is_correct)

    def test_06_and_07_level_progression_and_failed_level_stopping(self):
        """6. Verify level progression & 7. Verify failed level stops progression."""
        # Start intermediate requirement attempt
        start_res = self.client.post("/assessment/start", json={
            "skill": "JavaScript",
            "required_level": "intermediate"
        }).json()
        attempt_id = start_res["attempt_id"]
        basic_questions = start_res["questions"]

        # Answer 5 basic questions with 5/5 correct
        next_questions = None
        for q in basic_questions:
            # fetch actual correct answer from DB for testing verification
            q_db = self.db.query(AssessmentQuestion).filter(AssessmentQuestion.id == q["id"]).first()
            ans_res = self.client.post("/assessment/answer", json={
                "attempt_id": attempt_id,
                "question_id": q["id"],
                "selected_answer": q_db.correct_answer
            }).json()
            if ans_res.get("level_completed"):
                self.assertTrue(ans_res["level_passed"])
                self.assertFalse(ans_res["attempt_completed"])
                next_questions = ans_res["next_questions"]

        # 6. Verify level progression: received intermediate questions
        self.assertIsNotNone(next_questions)
        self.assertEqual(len(next_questions), 5)
        self.assertEqual(next_questions[0]["level"], "intermediate")

        # 7. Fail intermediate level by answering wrong answers (0/5 correct)
        final_ans_res = None
        for q in next_questions:
            q_db = self.db.query(AssessmentQuestion).filter(AssessmentQuestion.id == q["id"]).first()
            wrong_ans = "D" if q_db.correct_answer != "D" else "C"
            final_ans_res = self.client.post("/assessment/answer", json={
                "attempt_id": attempt_id,
                "question_id": q["id"],
                "selected_answer": wrong_ans
            }).json()

        self.assertTrue(final_ans_res["level_completed"])
        self.assertFalse(final_ans_res["level_passed"])
        self.assertTrue(final_ans_res["attempt_completed"])
        # Recorded highest level successfully demonstrated is basic!
        self.assertEqual(final_ans_res["assessed_level"], "basic")

    def test_08_intermediate_requirement_no_advanced_questions(self):
        """8. Verify intermediate requirement does not ask advanced questions."""
        start_res = self.client.post("/assessment/start", json={
            "skill": "React",
            "required_level": "intermediate"
        }).json()
        attempt_id = start_res["attempt_id"]

        # Complete basic (5/5) and intermediate (5/5)
        for level in ["basic", "intermediate"]:
            status_res = self.client.get(f"/assessment/{attempt_id}").json()
            for q in status_res["questions"]:
                q_db = self.db.query(AssessmentQuestion).filter(AssessmentQuestion.id == q["id"]).first()
                self.client.post("/assessment/answer", json={
                    "attempt_id": attempt_id,
                    "question_id": q["id"],
                    "selected_answer": q_db.correct_answer
                })

        final_status = self.client.get(f"/assessment/{attempt_id}").json()
        self.assertTrue(final_status["is_completed"])
        self.assertEqual(final_status["assessed_level"], "intermediate")

    def test_09_advanced_requirement_all_three_levels(self):
        """9. Verify advanced requirement can progress through all three levels."""
        start_res = self.client.post("/assessment/start", json={
            "skill": "PostgreSQL",
            "required_level": "advanced"
        }).json()
        attempt_id = start_res["attempt_id"]

        for level in ["basic", "intermediate", "advanced"]:
            status_res = self.client.get(f"/assessment/{attempt_id}").json()
            for q in status_res["questions"]:
                q_db = self.db.query(AssessmentQuestion).filter(AssessmentQuestion.id == q["id"]).first()
                self.client.post("/assessment/answer", json={
                    "attempt_id": attempt_id,
                    "question_id": q["id"],
                    "selected_answer": q_db.correct_answer
                })

        final_status = self.client.get(f"/assessment/{attempt_id}").json()
        self.assertTrue(final_status["is_completed"])
        self.assertEqual(final_status["assessed_level"], "advanced")

    def test_10_correct_answers_never_returned(self):
        """10. Verify correct answers are never returned in question API responses."""
        start_res = self.client.post("/assessment/start", json={
            "skill": "JavaScript",
            "required_level": "advanced"
        }).json()

        def check_no_correct_answer(data_obj):
            if isinstance(data_obj, dict):
                self.assertNotIn("correct_answer", data_obj)
                for k, v in data_obj.items():
                    check_no_correct_answer(v)
            elif isinstance(data_obj, list):
                for item in data_obj:
                    check_no_correct_answer(item)

        check_no_correct_answer(start_res)

        get_res = self.client.get(f"/assessment/{start_res['attempt_id']}").json()
        check_no_correct_answer(get_res)

    def test_11_duplicate_answers_rejected(self):
        """11. Verify duplicate answers for the same question are rejected."""
        start_res = self.client.post("/assessment/start", json={
            "skill": "JavaScript",
            "required_level": "basic"
        }).json()
        attempt_id = start_res["attempt_id"]
        q1_id = start_res["questions"][0]["id"]

        # First submission
        r1 = self.client.post("/assessment/answer", json={
            "attempt_id": attempt_id,
            "question_id": q1_id,
            "selected_answer": "A"
        })
        self.assertEqual(r1.status_code, 200)

        # Second submission -> duplicate!
        r2 = self.client.post("/assessment/answer", json={
            "attempt_id": attempt_id,
            "question_id": q1_id,
            "selected_answer": "A"
        })
        self.assertEqual(r2.status_code, 400)
        self.assertIn("Duplicate answer", r2.json()["detail"])

    def test_12_invalid_question_ids_handled(self):
        """12. Verify invalid question IDs are handled."""
        start_res = self.client.post("/assessment/start", json={
            "skill": "JavaScript",
            "required_level": "basic"
        }).json()
        attempt_id = start_res["attempt_id"]

        r = self.client.post("/assessment/answer", json={
            "attempt_id": attempt_id,
            "question_id": 99999,
            "selected_answer": "A"
        })
        self.assertEqual(r.status_code, 404)

    def test_13_invalid_answer_values_rejected(self):
        """13. Verify invalid answer values such as 'E' are rejected."""
        start_res = self.client.post("/assessment/start", json={
            "skill": "JavaScript",
            "required_level": "basic"
        }).json()
        attempt_id = start_res["attempt_id"]
        q1_id = start_res["questions"][0]["id"]

        r = self.client.post("/assessment/answer", json={
            "attempt_id": attempt_id,
            "question_id": q1_id,
            "selected_answer": "E"
        })
        self.assertEqual(r.status_code, 422)  # Pydantic validation error or 400

    def test_14_incomplete_assessments_cannot_be_marked_completed(self):
        """14. Verify incomplete assessments cannot be marked completed incorrectly."""
        start_res = self.client.post("/assessment/start", json={
            "skill": "React",
            "required_level": "basic"
        }).json()
        attempt_id = start_res["attempt_id"]

        # Only answer 2 of 5 questions
        for q in start_res["questions"][:2]:
            self.client.post("/assessment/answer", json={
                "attempt_id": attempt_id,
                "question_id": q["id"],
                "selected_answer": "A"
            })

        comp_res = self.client.post(f"/assessment/{attempt_id}/complete")
        self.assertEqual(comp_res.status_code, 400)
        self.assertIn("still in progress", comp_res.json()["detail"])


if __name__ == "__main__":
    unittest.main()
