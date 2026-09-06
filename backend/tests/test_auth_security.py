import os
import sys
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import SessionLocal

class TestAuthSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        self.db = SessionLocal()
        # Clean up
        self.db.execute(text("DELETE FROM assessment_attempts WHERE user_id IN (801, 802)"))
        self.db.execute(text("DELETE FROM users WHERE email IN ('cand_a@example.com', 'cand_b@example.com')"))
        self.db.commit()

        # Create Candidate A
        self.client.post("/users", json={"name": "Candidate A", "email": "cand_a@example.com", "password": "passA"})
        self.cand_a_id = self.db.execute(text("SELECT id FROM users WHERE email = 'cand_a@example.com'")).scalar()
        
        # Create Candidate B
        self.client.post("/users", json={"name": "Candidate B", "email": "cand_b@example.com", "password": "passB"})
        self.cand_b_id = self.db.execute(text("SELECT id FROM users WHERE email = 'cand_b@example.com'")).scalar()
        
        # Get Candidate A Token
        res_a = self.client.post("/login", data={"username": "cand_a@example.com", "password": "passA"})
        self.token_a = res_a.json()["access_token"]
        
        # Get Candidate B Token
        res_b = self.client.post("/login", data={"username": "cand_b@example.com", "password": "passB"})
        self.token_b = res_b.json()["access_token"]

    def tearDown(self):
        self.db.close()

    def test_valid_and_invalid_login(self):
        # Valid login
        res = self.client.post("/login", data={"username": "cand_a@example.com", "password": "passA"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("access_token", res.json())
        
        # Invalid login
        res = self.client.post("/login", data={"username": "cand_a@example.com", "password": "wrongpassword"})
        self.assertEqual(res.status_code, 401)

    def test_protected_endpoint_without_auth(self):
        # Attempt to access attempt status without token
        res = self.client.get("/assessment/1")
        self.assertEqual(res.status_code, 401)

    def test_cross_candidate_access(self):
        # Candidate A starts an assessment
        start_res = self.client.post("/assessment/start", json={
            "skill": "JavaScript", "required_level": "basic", "user_id": self.cand_a_id
        }, headers={"Authorization": f"Bearer {self.token_a}"})
        attempt_id = start_res.json()["attempt_id"]
        q_id = start_res.json()["questions"][0]["id"]
        
        # Candidate A accesses own attempt
        res = self.client.get(f"/assessment/{attempt_id}", headers={"Authorization": f"Bearer {self.token_a}"})
        self.assertEqual(res.status_code, 200)
        
        # Candidate B cannot access Candidate A's attempt
        res = self.client.get(f"/assessment/{attempt_id}", headers={"Authorization": f"Bearer {self.token_b}"})
        self.assertEqual(res.status_code, 403)
        
        # Candidate B cannot answer Candidate A's attempt
        res = self.client.post("/assessment/answer", json={
            "attempt_id": attempt_id, "question_id": q_id, "selected_answer": "A"
        }, headers={"Authorization": f"Bearer {self.token_b}"})
        self.assertEqual(res.status_code, 403)
        
        # Candidate B cannot complete Candidate A's attempt
        res = self.client.post(f"/assessment/{attempt_id}/complete", headers={"Authorization": f"Bearer {self.token_b}"})
        self.assertEqual(res.status_code, 403)
        
        # Candidate B cannot access Candidate A's history
        res = self.client.get(f"/assessment/history/{self.cand_a_id}", headers={"Authorization": f"Bearer {self.token_b}"})
        self.assertEqual(res.status_code, 403)

    def test_guest_attempt_isolation(self):
        # Create a guest attempt (no user_id, no token)
        start_res = self.client.post("/assessment/start", json={
            "skill": "JavaScript", "required_level": "basic"
        })
        self.assertEqual(start_res.status_code, 201)
        attempt_id = start_res.json()["attempt_id"]
        q_id = start_res.json()["questions"][0]["id"]
        
        # Guest cannot access it via GET /{attempt_id} (returns 401 Unauthorized because endpoint requires auth)
        res = self.client.get(f"/assessment/{attempt_id}")
        self.assertEqual(res.status_code, 401)
        
        # Even Candidate A cannot access the guest attempt because attempt.user_id (None) != Candidate A's ID
        res = self.client.get(f"/assessment/{attempt_id}", headers={"Authorization": f"Bearer {self.token_a}"})
        self.assertEqual(res.status_code, 403)

if __name__ == "__main__":
    unittest.main()
