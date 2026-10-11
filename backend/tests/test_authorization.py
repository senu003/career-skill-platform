import os
import sys
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import text
import json

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import SessionLocal
from app.models import CV

class TestAuthorizationSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.db = SessionLocal()
        # Clean up
        self.db.execute(text("DELETE FROM analyses WHERE user_id IN (SELECT id FROM users WHERE email IN ('sec_a@example.com', 'sec_b@example.com'))"))
        self.db.execute(text("DELETE FROM cvs WHERE user_id IN (SELECT id FROM users WHERE email IN ('sec_a@example.com', 'sec_b@example.com'))"))
        self.db.execute(text("DELETE FROM assessment_attempts WHERE user_id IN (SELECT id FROM users WHERE email IN ('sec_a@example.com', 'sec_b@example.com'))"))
        self.db.execute(text("DELETE FROM users WHERE email IN ('sec_a@example.com', 'sec_b@example.com')"))
        self.db.commit()

        # Create Candidate A
        self.client.post("/users", json={"name": "Sec A", "email": "sec_a@example.com", "password": "passA"})
        self.user_a_id = self.db.execute(text("SELECT id FROM users WHERE email = 'sec_a@example.com'")).scalar()
        
        # Create Candidate B
        self.client.post("/users", json={"name": "Sec B", "email": "sec_b@example.com", "password": "passB"})
        self.user_b_id = self.db.execute(text("SELECT id FROM users WHERE email = 'sec_b@example.com'")).scalar()
        
        # Get Candidate A Token
        res_a = self.client.post("/login", data={"username": "sec_a@example.com", "password": "passA"})
        self.token_a = res_a.json()["access_token"]
        self.headers_a = {"Authorization": f"Bearer {self.token_a}"}
        
        # Get Candidate B Token
        res_b = self.client.post("/login", data={"username": "sec_b@example.com", "password": "passB"})
        self.token_b = res_b.json()["access_token"]
        self.headers_b = {"Authorization": f"Bearer {self.token_b}"}

        # Create CV for Candidate A directly in DB
        cv = CV(user_id=self.user_a_id, file_name="resume_a.pdf", file_path="uploads/mock_a.pdf")
        self.db.add(cv)
        self.db.commit()
        self.db.refresh(cv)
        self.cv_a_id = cv.id

    def tearDown(self):
        self.db.execute(text("DELETE FROM analyses WHERE user_id IN (:u1, :u2)"), {"u1": self.user_a_id, "u2": self.user_b_id})
        self.db.execute(text("DELETE FROM cvs WHERE user_id IN (:u1, :u2)"), {"u1": self.user_a_id, "u2": self.user_b_id})
        self.db.execute(text("DELETE FROM assessment_attempts WHERE user_id IN (:u1, :u2)"), {"u1": self.user_a_id, "u2": self.user_b_id})
        self.db.execute(text("DELETE FROM users WHERE email IN ('sec_a@example.com', 'sec_b@example.com')"))
        self.db.commit()
        self.db.close()

    def test_start_assessment_idor(self):
        # User A tries to start assessment for User A
        res = self.client.post("/assessment/start", json={
            "skill": "JavaScript", "required_level": "intermediate", "user_id": self.user_a_id
        }, headers=self.headers_a)
        self.assertEqual(res.status_code, 201)

        # User A tries to start assessment for User B (IDOR bypass attempt)
        res = self.client.post("/assessment/start", json={
            "skill": "JavaScript", "required_level": "intermediate", "user_id": self.user_b_id
        }, headers=self.headers_a)
        self.assertEqual(res.status_code, 403, "Should prevent user A from starting assessment for user B")

        # Unauthenticated user tries to start assessment for User B
        res = self.client.post("/assessment/start", json={
            "skill": "JavaScript", "required_level": "intermediate", "user_id": self.user_b_id
        })
        self.assertEqual(res.status_code, 401, "Should require auth to specify user_id")

    def test_get_assessment_result_skill_idor(self):
        # User A tries to get result for User B
        res = self.client.get(f"/assessment/result/JavaScript?user_id={self.user_b_id}", headers=self.headers_a)
        self.assertEqual(res.status_code, 403, "Should prevent user A from getting skill result for user B")
        
        # Unauthenticated user tries to get result for User A
        res = self.client.get(f"/assessment/result/JavaScript?user_id={self.user_a_id}")
        self.assertEqual(res.status_code, 401, "Should require auth to specify user_id")

    def test_cv_analyze_user_id_idor(self):
        requirements = json.dumps([{"skill": "JavaScript", "level": "intermediate", "importance": "required"}])
        
        # User A tries to analyze CV on behalf of User B
        res = self.client.post(
            "/cv/analyze",
            data={"requirements": requirements, "user_id": self.user_b_id},
            headers=self.headers_a
        )
        self.assertEqual(res.status_code, 403, "Should prevent user A from analyzing CV for user B")

        # Unauthenticated user tries to analyze CV on behalf of User B
        res = self.client.post(
            "/cv/analyze",
            data={"requirements": requirements, "user_id": self.user_b_id}
        )
        self.assertEqual(res.status_code, 401, "Should require auth to specify user_id")
        
    def test_cv_analyze_cv_id_idor(self):
        requirements = json.dumps([{"skill": "Python", "level": "intermediate", "importance": "required"}])
        
        # User B tries to analyze CV using User A's cv_id
        res = self.client.post(
            "/cv/analyze",
            data={"requirements": requirements, "cv_id": self.cv_a_id},
            headers=self.headers_b
        )
        self.assertEqual(res.status_code, 403, "Should prevent user B from analyzing User A's CV")

if __name__ == "__main__":
    unittest.main()
