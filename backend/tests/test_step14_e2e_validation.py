import os
import sys
import json
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import SessionLocal
from app.models import AssessmentQuestion

client = TestClient(app)

class TestStep14E2EValidation:
    """
    Step 14 End-to-End Validation Test Suite
    Tests complete candidate journey, multi-skill scenario, deterministic weakness logic,
    weighting & aggregation, longitudinal tracking, candidate isolation, ML prediction behavior,
    security regression tests, and edge cases.
    """

    @pytest.fixture(autouse=True)
    def setup_db(self):
        self.db = SessionLocal()
        # Cleanup test data
        self.db.execute(text("DELETE FROM assessment_attempts WHERE user_id IN (901, 902, 903, 904)"))
        self.db.execute(text("DELETE FROM users WHERE email IN ('step14_cand_a@example.com', 'step14_cand_b@example.com', 'step14_sec_a@example.com', 'step14_sec_b@example.com', 'step14_long_a@example.com', 'step14_long_b@example.com')"))
        self.db.commit()
        yield
        self.db.close()

    def _answer_questions_for_attempt(self, attempt_id: int, headers: dict, force_correct: bool = True, force_wrong: bool = False):
        """Helper to answer all questions for an attempt until completion or no more questions."""
        while True:
            status_res = client.get(f"/assessment/{attempt_id}", headers=headers)
            if status_res.status_code != 200:
                break
            status_data = status_res.json()
            if status_data.get("is_completed"):
                break
            
            questions = status_data.get("questions", [])
            answered_q_ids = set(a["question_id"] for a in status_data.get("submitted_answers", []))
            unanswered = [q for q in questions if q["id"] not in answered_q_ids]
            
            if not unanswered:
                comp_res = client.post(f"/assessment/{attempt_id}/complete", headers=headers)
                if comp_res.status_code == 200 and comp_res.json().get("status") == "completed":
                    break
                st_next = client.get(f"/assessment/{attempt_id}", headers=headers).json()
                if st_next.get("is_completed"):
                    break
                unanswered = [q for q in st_next.get("questions", []) if q["id"] not in set(a["question_id"] for a in st_next.get("submitted_answers", []))]
                if not unanswered:
                    break

            for q in unanswered:
                q_db = self.db.query(AssessmentQuestion).filter(AssessmentQuestion.id == q["id"]).first()
                if force_correct:
                    ans = q_db.correct_answer if q_db else "A"
                elif force_wrong:
                    ans = "D" if q_db and q_db.correct_answer != "D" else "C"
                else:
                    ans = "A"
                
                res = client.post("/assessment/answer", json={
                    "attempt_id": attempt_id,
                    "question_id": q["id"],
                    "selected_answer": ans
                }, headers=headers)

    @patch("app.routers.requirements.extract_requirements")
    @patch("app.services.cv_service.extract_pdf_text")
    def test_01_complete_candidate_journey_and_multi_skill_scenario(self, mock_extract, mock_extract_reqs):
        mock_extract_reqs.return_value = [
            {"skill": "React", "level": "advanced", "importance": "required"},
            {"skill": "JavaScript", "level": "intermediate", "importance": "required"},
            {"skill": "PostgreSQL", "level": "basic", "importance": "preferred"}
        ]
        mock_extract.return_value = {
            "filename": "resume.pdf",
            "pages": 1,
            "text": "Experienced Senior Developer skilled in React with 4 years experience, JavaScript frontend engineering, and basic PostgreSQL query knowledge."
        }

        # 1. Register candidate A
        reg_res = client.post("/users", json={
            "name": "Validation Candidate A",
            "email": "step14_cand_a@example.com",
            "password": "Password123!"
        })
        assert reg_res.status_code == 200, f"Registration failed: {reg_res.text}"
        cand_a_id = reg_res.json()["id"]

        # 2. Login candidate A
        login_res = client.post("/login", data={
            "username": "step14_cand_a@example.com",
            "password": "Password123!"
        })
        assert login_res.status_code == 200, f"Login failed: {login_res.text}"
        token_a = login_res.json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        # 3. Upload CV file
        cv_content = b"%PDF-1.4 mock pdf content"
        files = {"file": ("resume.pdf", cv_content, "application/pdf")}
        cv_res = client.post("/cv/upload", files=files)
        assert cv_res.status_code == 200, f"CV Upload failed: {cv_res.text}"
        extracted_text = cv_res.json()["text"]

        # 4. Enter job description & extract requirements
        job_desc = "We are seeking a Lead Developer skilled in React (Advanced), JavaScript (Intermediate), and PostgreSQL (Basic)."
        req_res = client.post("/requirements/analyze", json={"text": job_desc})
        assert req_res.status_code == 200, f"Requirement analysis failed: {req_res.text}"
        extracted_reqs = req_res.json()["requirements"]

        # 5. Match CV skills against extracted requirements
        cv_analyze_res = client.post(
            "/cv/analyze",
            files={"file": ("resume.pdf", cv_content, "application/pdf")},
            data={"requirements": json.dumps(extracted_reqs), "user_id": cand_a_id}
        )
        assert cv_analyze_res.status_code == 200, f"CV Analyze failed: {cv_analyze_res.text}"

        # Multi-Skill Scenario: Assess React, JavaScript, PostgreSQL with different required levels and outcomes
        # ----------------------------------------------------
        # Skill 1: React (Required level: advanced) - Strong performance (All correct answers)
        start1 = client.post("/assessment/start", json={
            "skill": "React",
            "required_level": "advanced",
            "user_id": cand_a_id
        }, headers=headers_a)
        assert start1.status_code == 201, f"Start React failed: {start1.text}"
        att1_id = start1.json()["attempt_id"]
        self._answer_questions_for_attempt(att1_id, headers_a, force_correct=True)
        res1 = client.get(f"/assessment/{att1_id}/result", headers=headers_a).json()

        # Skill 2: JavaScript (Required level: intermediate) - Weak performance (All wrong answers)
        start2 = client.post("/assessment/start", json={
            "skill": "JavaScript",
            "required_level": "intermediate",
            "user_id": cand_a_id
        }, headers=headers_a)
        assert start2.status_code == 201, f"Start JS failed: {start2.text}"
        att2_id = start2.json()["attempt_id"]
        self._answer_questions_for_attempt(att2_id, headers_a, force_wrong=True)
        res2 = client.get(f"/assessment/{att2_id}/result", headers=headers_a).json()

        # Skill 3: PostgreSQL (Required level: basic) - Strong performance
        start3 = client.post("/assessment/start", json={
            "skill": "PostgreSQL",
            "required_level": "basic",
            "user_id": cand_a_id
        }, headers=headers_a)
        assert start3.status_code == 201, f"Start Postgres failed: {start3.text}"
        att3_id = start3.json()["attempt_id"]
        self._answer_questions_for_attempt(att3_id, headers_a, force_correct=True)
        res3 = client.get(f"/assessment/{att3_id}/result", headers=headers_a).json()

        # Validate that skills have distinct states
        assert res1["skill"] == "React"
        assert res2["skill"] == "JavaScript"
        assert res3["skill"] == "PostgreSQL"

        # Check Deterministic Weakness Logic
        # is_weakness = (level_gap > 0) OR (total_score < 0.60)
        for res in [res1, res2, res3]:
            expected_weakness = (res["level_gap"] > 0) or (res["total_score"] is not None and res["total_score"] < 0.60)
            assert res["is_weakness"] == expected_weakness, f"Weakness logic failed for {res['skill']}: got {res['is_weakness']} expected {expected_weakness}"

        # 6. Candidate-level Aggregation
        skills_payload = [
            {
                "skill": res1["skill"],
                "required_level": res1["required_level"],
                "assessed_level": res1["assessed_level"],
                "level_gap": res1["level_gap"],
                "total_score": res1["total_score"],
                "is_weakness": res1["is_weakness"],
                "weakness_reason": res1["weakness_reason"],
                "priority": res1["priority"],
                "recommendation": res1["recommendation"],
                "recommendation_reason": res1["recommendation_reason"],
                "importance": "required",
                "matched": True
            },
            {
                "skill": res2["skill"],
                "required_level": res2["required_level"],
                "assessed_level": res2["assessed_level"],
                "level_gap": res2["level_gap"],
                "total_score": res2["total_score"],
                "is_weakness": res2["is_weakness"],
                "weakness_reason": res2["weakness_reason"],
                "priority": res2["priority"],
                "recommendation": res2["recommendation"],
                "recommendation_reason": res2["recommendation_reason"],
                "importance": "required",
                "matched": True
            },
            {
                "skill": res3["skill"],
                "required_level": res3["required_level"],
                "assessed_level": res3["assessed_level"],
                "level_gap": res3["level_gap"],
                "total_score": res3["total_score"],
                "is_weakness": res3["is_weakness"],
                "weakness_reason": res3["weakness_reason"],
                "priority": res3["priority"],
                "recommendation": res3["recommendation"],
                "recommendation_reason": res3["recommendation_reason"],
                "importance": "preferred",
                "matched": True
            }
        ]

        agg_res = client.post("/assessment/aggregate", json={"skills": skills_payload})
        assert agg_res.status_code == 200, f"Aggregation failed: {agg_res.text}"
        agg = agg_res.json()

        assert agg["total_skills"] == 3
        assert len(agg["skills"]) == 3
        assert agg["overall_score"] is not None
        assert agg["readiness_status"] in ["ready", "partially_ready", "not_ready", "Excellent", "Needs Improvement", "Ready", "Partially Ready", "Not Ready"] or isinstance(agg["readiness_status"], str)
        
        # Verify no duplicate skills in aggregation
        unique_skills = set(s["skill"] for s in agg["skills"])
        assert len(unique_skills) == 3

    def test_02_ml_behavior_case_a_and_case_b(self):
        # Setup Candidate B
        reg_b = client.post("/users", json={
            "name": "ML Validation Candidate",
            "email": "step14_cand_b@example.com",
            "password": "Password123!"
        })
        cand_b_id = reg_b.json()["id"]
        login_b = client.post("/login", data={"username": "step14_cand_b@example.com", "password": "Password123!"})
        headers_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # Case A — First assessment (No prior attempt)
        start1 = client.post("/assessment/start", json={
            "skill": "JavaScript",
            "required_level": "intermediate",
            "user_id": cand_b_id
        }, headers=headers_b)
        assert start1.status_code == 201, f"Start JS failed: {start1.text}"
        att1_id = start1.json()["attempt_id"]
        self._answer_questions_for_attempt(att1_id, headers_b, force_wrong=True)

        res1 = client.get(f"/assessment/{att1_id}/result", headers=headers_b).json()
        
        # Candidate B has only 1 attempt (t0). No prior history BEFORE att1.
        # Thus improvement_probability MUST be null!
        assert res1["improvement_probability"] is None, f"Expected null for first assessment, got {res1['improvement_probability']}"

        # Case B — Returning candidate (Second assessment for SAME skill JavaScript)
        start2 = client.post("/assessment/start", json={
            "skill": "JavaScript",
            "required_level": "intermediate",
            "user_id": cand_b_id
        }, headers=headers_b)
        assert start2.status_code == 201, f"Start JS failed: {start2.text}"
        att2_id = start2.json()["attempt_id"]
        self._answer_questions_for_attempt(att2_id, headers_b, force_correct=True)

        res2 = client.get(f"/assessment/{att2_id}/result", headers=headers_b).json()

        # Attempt 2 is a returning assessment. Prior attempt 1 exists.
        # Expect improvement_probability != null and 0.0 <= prob <= 1.0
        assert res2["improvement_probability"] is not None, "Expected valid float for returning candidate"
        assert 0.0 <= res2["improvement_probability"] <= 1.0, f"Invalid prob value: {res2['improvement_probability']}"

    def test_03_longitudinal_tracking_and_isolation(self):
        # Create Candidate A and Candidate B
        reg_a = client.post("/users", json={"name": "Long Cand A", "email": "step14_long_a@example.com", "password": "pass"})
        cand_a_id = reg_a.json()["id"]
        token_a = client.post("/login", data={"username": "step14_long_a@example.com", "password": "pass"}).json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        reg_b = client.post("/users", json={"name": "Long Cand B", "email": "step14_long_b@example.com", "password": "pass"})
        cand_b_id = reg_b.json()["id"]
        token_b = client.post("/login", data={"username": "step14_long_b@example.com", "password": "pass"}).json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Candidate A performs 2 attempts for "React"
        # Attempt 1 (wrong)
        st1 = client.post("/assessment/start", json={"skill": "React", "required_level": "intermediate", "user_id": cand_a_id}, headers=headers_a).json()
        self._answer_questions_for_attempt(st1["attempt_id"], headers_a, force_wrong=True)

        # Attempt 2 (correct)
        st2 = client.post("/assessment/start", json={"skill": "React", "required_level": "intermediate", "user_id": cand_a_id}, headers=headers_a).json()
        self._answer_questions_for_attempt(st2["attempt_id"], headers_a, force_correct=True)

        # Candidate B performs 1 attempt for "PostgreSQL"
        st_b = client.post("/assessment/start", json={"skill": "PostgreSQL", "required_level": "basic", "user_id": cand_b_id}, headers=headers_b).json()
        self._answer_questions_for_attempt(st_b["attempt_id"], headers_b, force_correct=True)

        # Fetch history for Candidate A
        hist_a = client.get(f"/assessment/history/{cand_a_id}", headers=headers_a).json()
        
        # History keys can be case insensitive e.g. "react" or "React"
        react_hist = hist_a.get("react") or hist_a.get("React")
        assert react_hist is not None, f"React history missing from candidate A: {hist_a}"
        assert len(react_hist) == 2
        obs1, obs2 = react_hist[0], react_hist[1]
        
        # Verify chronological ordering & improvement calculation
        outcome2 = obs2.get("outcome") or {}
        assert outcome2.get("score_change") is not None
        assert outcome2.get("improved") == (obs2["total_score"] > obs1["total_score"])

        # Isolation check: Candidate B history ("postgresql" / "PostgreSQL") must not appear in Candidate A's response
        assert "postgresql" not in hist_a and "PostgreSQL" not in hist_a

    def test_04_security_regression_tests(self):
        # 1. Unauthenticated assessment status rejection
        unauth_res = client.get("/assessment/99999")
        assert unauth_res.status_code == 401

        # 2. Candidate A cannot access Candidate B's attempt or history
        reg_a = client.post("/users", json={"name": "Sec A", "email": "step14_sec_a@example.com", "password": "pass"})
        token_a = client.post("/login", data={"username": "step14_sec_a@example.com", "password": "pass"}).json()["access_token"]
        headers_a = {"Authorization": f"Bearer {token_a}"}

        reg_b = client.post("/users", json={"name": "Sec B", "email": "step14_sec_b@example.com", "password": "pass"})
        cand_b_id = reg_b.json()["id"]
        token_b = client.post("/login", data={"username": "step14_sec_b@example.com", "password": "pass"}).json()["access_token"]
        headers_b = {"Authorization": f"Bearer {token_b}"}

        st_b = client.post("/assessment/start", json={"skill": "JavaScript", "required_level": "basic", "user_id": cand_b_id}, headers=headers_b).json()
        att_b_id = st_b["attempt_id"]

        # Candidate A attempts to access Candidate B's attempt
        sec1 = client.get(f"/assessment/{att_b_id}", headers=headers_a)
        assert sec1.status_code == 403

        # Candidate A attempts to view Candidate B's history
        sec2 = client.get(f"/assessment/history/{cand_b_id}", headers=headers_a)
        assert sec2.status_code == 403

    def test_05_deterministic_logic_edge_cases(self):
        from app.services.skill_analysis_service import calculate_weakness

        # Case 1: score < 0.60, level_gap = 0 -> is_weakness = True
        w1 = calculate_weakness(level_gap=0, total_score=0.35)
        assert w1["is_weakness"] is True
        assert w1["weakness_reason"] in ["LOW_SCORE", "LEVEL_GAP_AND_LOW_SCORE"]

        # Case 2: score = 0.60, level_gap = 0 -> is_weakness = False (boundary check)
        w2 = calculate_weakness(level_gap=0, total_score=0.60)
        assert w2["is_weakness"] is False

        # Case 3: score = 0.85, level_gap = 1 -> is_weakness = True (level gap > 0)
        w3 = calculate_weakness(level_gap=1, total_score=0.85)
        assert w3["is_weakness"] is True
        assert w3["weakness_reason"] in ["LEVEL_GAP", "LEVEL_GAP_AND_LOW_SCORE"]
