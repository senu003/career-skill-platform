import os
import sys
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import text
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import SessionLocal
from app.models import AssessmentQuestion, AssessmentAttempt, AssessmentAnswer


class TestInterviewPrepService(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.db = SessionLocal()
        self.db.execute(text("DELETE FROM assessment_answers WHERE attempt_id IN (SELECT id FROM assessment_attempts WHERE user_id IN (SELECT id FROM users WHERE email IN ('test_prep_user_a@example.com', 'test_prep_user_b@example.com')))"))
        self.db.execute(text("DELETE FROM assessment_attempts WHERE user_id IN (SELECT id FROM users WHERE email IN ('test_prep_user_a@example.com', 'test_prep_user_b@example.com'))"))
        self.db.execute(text("DELETE FROM users WHERE email IN ('test_prep_user_a@example.com', 'test_prep_user_b@example.com')"))
        self.db.commit()

        # Create user A
        self.client.post("/users", json={
            "name": "Prep User A",
            "email": "test_prep_user_a@example.com",
            "password": "password123"
        })
        login_a = self.client.post("/login", data={
            "username": "test_prep_user_a@example.com",
            "password": "password123"
        }).json()
        self.token_a = login_a["access_token"]
        self.user_a_id = self.db.execute(text("SELECT id FROM users WHERE email = 'test_prep_user_a@example.com'")).scalar()
        self.headers_a = {"Authorization": f"Bearer {self.token_a}"}

    def tearDown(self):
        self.db.execute(text("DELETE FROM assessment_answers WHERE attempt_id IN (SELECT id FROM assessment_attempts WHERE user_id = :uid)"), {"uid": self.user_a_id})
        self.db.execute(text("DELETE FROM assessment_attempts WHERE user_id = :uid"), {"uid": self.user_a_id})
        self.db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": self.user_a_id})
        self.db.commit()
        self.db.close()

    def test_01_summary_empty_state(self):
        """When user has 0 attempts, summary returns all 5 supported skills with not_started status."""
        res = self.client.get("/assessment/interview-prep/summary", headers=self.headers_a)
        self.assertEqual(res.status_code, 200)
        data = res.json()

        self.assertEqual(data["total_attempts"], 0)
        self.assertEqual(data["skills_practised"], 0)
        self.assertGreaterEqual(data["skills_supported_count"], 5)
        self.assertGreaterEqual(len(data["skills"]), 5)

        python_meta = next(s for s in data["skills"] if s["skill"] == "Python")
        self.assertEqual(python_meta["attempts_count"], 0)
        self.assertEqual(python_meta["trend"], "not_started")
        self.assertEqual(python_meta["trend_label"], "Not Started")
        self.assertIsNone(python_meta["latest_score"])

    def test_02_summary_and_skill_analysis_with_multiple_attempts(self):
        """Multiple attempts track chronological progression and delta vs first attempt."""
        q1 = AssessmentQuestion(
            skill="Python",
            level="basic",
            topic="Syntax",
            question="What is indentation in Python?",
            correct_answer="A",
            explanation="Defines code blocks.",
            interview_tip="Always mention PEP 8."
        )
        q2 = AssessmentQuestion(
            skill="Python",
            level="basic",
            topic="Syntax",
            question="Which keyword defines a function?",
            correct_answer="B",
            explanation="def keyword defines functions.",
            interview_tip="Functions are first class citizens."
        )
        self.db.add_all([q1, q2])
        self.db.commit()
        self.db.refresh(q1)
        self.db.refresh(q2)

        # Attempt 1: 1 correct, 1 incorrect = 50%
        att1 = AssessmentAttempt(
            user_id=self.user_a_id,
            skill="Python",
            required_level="basic",
            assessed_level="basic",
            completed_at=datetime.now(timezone.utc)
        )
        self.db.add(att1)
        self.db.commit()
        self.db.refresh(att1)

        ans1_1 = AssessmentAnswer(attempt_id=att1.id, question_id=q1.id, selected_answer="A", is_correct=True, time_taken=30.0)
        ans1_2 = AssessmentAnswer(attempt_id=att1.id, question_id=q2.id, selected_answer="C", is_correct=False, time_taken=20.0)
        self.db.add_all([ans1_1, ans1_2])

        # Attempt 2: 2 correct = 100% (Improving)
        att2 = AssessmentAttempt(
            user_id=self.user_a_id,
            skill="Python",
            required_level="intermediate",
            assessed_level="intermediate",
            completed_at=datetime.now(timezone.utc)
        )
        self.db.add(att2)
        self.db.commit()
        self.db.refresh(att2)

        ans2_1 = AssessmentAnswer(attempt_id=att2.id, question_id=q1.id, selected_answer="A", is_correct=True, time_taken=18.0)
        ans2_2 = AssessmentAnswer(attempt_id=att2.id, question_id=q2.id, selected_answer="B", is_correct=True, time_taken=16.0)
        self.db.add_all([ans2_1, ans2_2])
        self.db.commit()

        # Check summary
        sum_res = self.client.get("/assessment/interview-prep/summary", headers=self.headers_a)
        self.assertEqual(sum_res.status_code, 200)
        sum_data = sum_res.json()
        self.assertEqual(sum_data["total_attempts"], 2)
        self.assertEqual(sum_data["skills_practised"], 1)

        py_skill = next(s for s in sum_data["skills"] if s["skill"] == "Python")
        self.assertEqual(py_skill["attempts_count"], 2)
        self.assertEqual(py_skill["first_score_pct"], 50)
        self.assertEqual(py_skill["latest_score_pct"], 100)
        self.assertEqual(py_skill["trend"], "improving")

        # Check skill analysis
        skill_res = self.client.get("/assessment/interview-prep/skill/Python", headers=self.headers_a)
        self.assertEqual(skill_res.status_code, 200)
        skill_data = skill_res.json()

        self.assertEqual(skill_data["skill"], "Python")
        self.assertEqual(skill_data["total_attempts"], 2)
        self.assertEqual(skill_data["first_score_pct"], 50)
        self.assertEqual(skill_data["latest_score_pct"], 100)
        self.assertEqual(skill_data["score_delta_vs_first"], 50)
        self.assertEqual(len(skill_data["score_progression"]), 2)
        self.assertEqual(skill_data["score_progression"][0]["attempt_number"], 1)
        self.assertEqual(skill_data["score_progression"][1]["attempt_number"], 2)
        self.assertEqual(len(skill_data["past_attempts"]), 2)
        self.assertEqual(skill_data["past_attempts"][0]["attempt_id"], att2.id)

    def test_03_personalized_next_steps_priority(self):
        """Repeated mistakes trigger High Priority targeted practice recommendations."""
        q_topic1 = AssessmentQuestion(
            skill="PostgreSQL",
            level="basic",
            topic="Joins",
            question="What is an outer join?",
            correct_answer="B",
            explanation="Preserves unmatched rows."
        )
        q_topic2 = AssessmentQuestion(
            skill="PostgreSQL",
            level="basic",
            topic="Joins",
            question="What is a cross join?",
            correct_answer="C",
            explanation="Cartesian product of tables."
        )
        self.db.add_all([q_topic1, q_topic2])
        self.db.commit()
        self.db.refresh(q_topic1)
        self.db.refresh(q_topic2)

        att = AssessmentAttempt(
            user_id=self.user_a_id,
            skill="PostgreSQL",
            required_level="basic",
            completed_at=datetime.now(timezone.utc)
        )
        self.db.add(att)
        self.db.commit()
        self.db.refresh(att)

        ans1 = AssessmentAnswer(attempt_id=att.id, question_id=q_topic1.id, selected_answer="A", is_correct=False)
        ans2 = AssessmentAnswer(attempt_id=att.id, question_id=q_topic2.id, selected_answer="A", is_correct=False)
        self.db.add_all([ans1, ans2])
        self.db.commit()

        next_res = self.client.get("/assessment/interview-prep/next-steps", headers=self.headers_a)
        self.assertEqual(next_res.status_code, 200)
        next_data = next_res.json()

        self.assertTrue(next_data["has_data"])
        self.assertGreater(len(next_data["recommendations"]), 0)
        first_rec = next_data["recommendations"][0]
        self.assertEqual(first_rec["priority"], "high")
        self.assertEqual(first_rec["topic"], "Joins")
        self.assertIn("practice_url", first_rec)


if __name__ == "__main__":
    unittest.main()
