import os
import sys
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import SessionLocal
from app.models import AssessmentQuestion, AssessmentAttempt, AssessmentAnswer


class TestAssessmentReviewAndWeaknesses(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.db = SessionLocal()
        # Clean up test users and attempts
        self.db.execute(text("DELETE FROM assessment_answers WHERE attempt_id IN (SELECT id FROM assessment_attempts WHERE user_id IN (SELECT id FROM users WHERE email IN ('test_rev_user_a@example.com', 'test_rev_user_b@example.com')))"))
        self.db.execute(text("DELETE FROM assessment_attempts WHERE user_id IN (SELECT id FROM users WHERE email IN ('test_rev_user_a@example.com', 'test_rev_user_b@example.com'))"))
        self.db.execute(text("DELETE FROM users WHERE email IN ('test_rev_user_a@example.com', 'test_rev_user_b@example.com')"))
        self.db.commit()

        # Create user A
        self.client.post("/users", json={
            "name": "User A",
            "email": "test_rev_user_a@example.com",
            "password": "password123"
        })
        login_a = self.client.post("/login", data={
            "username": "test_rev_user_a@example.com",
            "password": "password123"
        }).json()
        self.token_a = login_a["access_token"]
        self.user_a_id = self.db.execute(text("SELECT id FROM users WHERE email = 'test_rev_user_a@example.com'")).scalar()

        # Create user B
        self.client.post("/users", json={
            "name": "User B",
            "email": "test_rev_user_b@example.com",
            "password": "password123"
        })
        login_b = self.client.post("/login", data={
            "username": "test_rev_user_b@example.com",
            "password": "password123"
        }).json()
        self.token_b = login_b["access_token"]
        self.user_b_id = self.db.execute(text("SELECT id FROM users WHERE email = 'test_rev_user_b@example.com'")).scalar()

    def tearDown(self):
        self.db.close()

    def test_01_empty_weaknesses_returns_friendly_message(self):
        """User with no completed attempts gets 200 with total_assessments=0 and guidance message."""
        headers = {"Authorization": f"Bearer {self.token_a}"}
        res = self.client.get("/assessment/revision/weaknesses", headers=headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["total_assessments_completed"], 0)
        self.assertEqual(len(data["weak_topics"]), 0)
        self.assertIn("Complete at least one assessment", data["message"])
        self.assertIsInstance(data["skills_summary"], list)
        self.assertGreaterEqual(len(data["skills_summary"]), 5)

    def test_02_assessment_review_flow_and_ownership(self):
        """Complete an assessment, verify review endpoint returns explanations & correct/incorrect data, and test ownership."""
        headers_a = {"Authorization": f"Bearer {self.token_a}"}
        headers_b = {"Authorization": f"Bearer {self.token_b}"}

        # 1. Start assessment
        start_res = self.client.post("/assessment/start", json={
            "skill": "PostgreSQL",
            "required_level": "basic",
            "user_id": self.user_a_id
        }, headers=headers_a)
        self.assertEqual(start_res.status_code, 201)
        attempt_id = start_res.json()["attempt_id"]
        questions = start_res.json()["questions"]
        self.assertEqual(len(questions), 5)

        # Incomplete attempt review should fail with 400
        incomp_res = self.client.get(f"/assessment/{attempt_id}/review", headers=headers_a)
        self.assertEqual(incomp_res.status_code, 400)
        self.assertIn("not yet completed", incomp_res.json()["detail"])

        # 2. Answer all 5 questions (answer first 2 correctly, remaining 3 incorrectly)
        for i, q in enumerate(questions):
            q_db = self.db.query(AssessmentQuestion).filter(AssessmentQuestion.id == q["id"]).first()
            assert q_db is not None
            if i < 2:
                ans = q_db.correct_answer
            else:
                # pick a wrong answer
                ans = "A" if q_db.correct_answer != "A" else "B"

            ans_res = self.client.post("/assessment/answer", json={
                "attempt_id": attempt_id,
                "question_id": q["id"],
                "selected_answer": ans,
                "time_taken": 15
            }, headers=headers_a)
            self.assertEqual(ans_res.status_code, 200)

        # 3. Retrieve review for User A
        rev_res = self.client.get(f"/assessment/{attempt_id}/review", headers=headers_a)
        self.assertEqual(rev_res.status_code, 200)
        rev_data = rev_res.json()
        self.assertEqual(rev_data["attempt_id"], attempt_id)
        self.assertEqual(rev_data["skill"], "PostgreSQL")
        self.assertEqual(rev_data["total_questions"], 5)
        self.assertEqual(rev_data["correct_answers"], 2)
        self.assertEqual(len(rev_data["questions"]), 5)

        first_q = rev_data["questions"][0]
        self.assertIn("question", first_q)
        self.assertIn("topic", first_q)
        self.assertIn("selected_answer", first_q)
        self.assertIn("correct_answer", first_q)
        self.assertTrue(first_q["is_correct"])
        self.assertIsNotNone(first_q["explanation"])
        self.assertIsNotNone(first_q["interview_tip"])

        # Check an incorrect question has misconception
        wrong_q = rev_data["questions"][2]
        self.assertFalse(wrong_q["is_correct"])
        self.assertIsNotNone(wrong_q["misconception"])

        # 4. Unauthorized User B cannot review User A's attempt (403 Forbidden)
        unauth_res = self.client.get(f"/assessment/{attempt_id}/review", headers=headers_b)
        self.assertEqual(unauth_res.status_code, 403)
        self.assertIn("Not authorized", unauth_res.json()["detail"])

    def test_03_weakness_finder_identifies_struggling_topics(self):
        """User A with incorrect answers should see weaknesses identified with explainable recommendations."""
        headers_a = {"Authorization": f"Bearer {self.token_a}"}

        # Start and complete a basic PostgreSQL assessment with wrong answers
        start_res = self.client.post("/assessment/start", json={
            "skill": "PostgreSQL",
            "required_level": "basic",
            "user_id": self.user_a_id
        }, headers=headers_a).json()

        attempt_id = start_res["attempt_id"]
        for q in start_res["questions"]:
            q_db = self.db.query(AssessmentQuestion).filter(AssessmentQuestion.id == q["id"]).first()
            assert q_db is not None
            # Deliberately pick wrong answer
            ans = "A" if q_db.correct_answer != "A" else "B"
            self.client.post("/assessment/answer", json={
                "attempt_id": attempt_id,
                "question_id": q["id"],
                "selected_answer": ans,
                "time_taken": 20
            }, headers=headers_a)

        # Fetch weaknesses
        weak_res = self.client.get("/assessment/revision/weaknesses", headers=headers_a)
        self.assertEqual(weak_res.status_code, 200)
        data = weak_res.json()

        self.assertGreaterEqual(data["total_assessments_completed"], 1)
        self.assertGreater(len(data["weak_topics"]), 0)

        # Check weak topic format and explainability
        weak_topic = data["weak_topics"][0]
        self.assertEqual(weak_topic["skill"], "PostgreSQL")
        self.assertGreater(weak_topic["incorrect_count"], 0)
        self.assertLess(weak_topic["accuracy_pct"], 70.0)
        self.assertIn("Review", weak_topic["recommendation"])
        self.assertIn("questions incorrectly", weak_topic["recommendation"])

        # Check skills summary has PostgreSQL recorded
        sql_summary = next((s for s in data["skills_summary"] if s["skill"] == "PostgreSQL"), None)
        self.assertIsNotNone(sql_summary)
        self.assertGreater(sql_summary["attempts_count"], 0)

    def test_04_targeted_start_with_topic_parameter(self):
        """Starting an assessment with a specific topic prioritizes that topic in question selection."""
        headers_a = {"Authorization": f"Bearer {self.token_a}"}
        res = self.client.post("/assessment/start", json={
            "skill": "PostgreSQL",
            "required_level": "basic",
            "topic": "Filtering",
            "user_id": self.user_a_id
        }, headers=headers_a)
        self.assertEqual(res.status_code, 201)
        data = res.json()
        questions = data["questions"]
        self.assertEqual(len(questions), 5)
        # Verify first question has the targeted topic
        topics = [q["topic"] for q in questions]
        self.assertIn("Filtering", topics)
        self.assertEqual(questions[0]["topic"], "Filtering")

