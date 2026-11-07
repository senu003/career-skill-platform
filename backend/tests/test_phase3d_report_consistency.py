import os
import sys
import unittest
from fastapi.testclient import TestClient
from sqlalchemy import text
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import SessionLocal
from app.models import (
    User,
    CV,
    Job,
    Analysis,
    AssessmentQuestion,
    AssessmentAttempt,
    AssessmentAnswer,
)
from app.services.skill_analysis_service import (
    select_eligible_assessment_attempt,
    get_assessment_result_for_skill,
    combine_cv_and_assessment,
)
from app.services.assessment_review_service import (
    get_assessment_review,
    get_user_weakness_analysis,
)
from app.services.aggregation_service import aggregate_final_assessment
from app.schemas.skill_analysis import FinalSkillItemSchema


class TestPhase3DReportConsistency(unittest.TestCase):
    """
    Test suite for CareerSkill Phase 3D: consistent assessment results across
    Skill Match, final report, question review, and History.
    """

    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def setUp(self):
        from app.rate_limiter import limiter
        self._limiter_was_enabled = getattr(limiter, "enabled", True)
        limiter.enabled = False

        self.db = SessionLocal()

        # Clean up test data
        self.db.execute(
            text(
                "DELETE FROM assessment_answers WHERE attempt_id IN "
                "(SELECT id FROM assessment_attempts WHERE user_id IN "
                "(SELECT id FROM users WHERE email IN ('test_p3d_user_a@example.com', 'test_p3d_user_b@example.com')))"
            )
        )
        self.db.execute(
            text(
                "DELETE FROM assessment_attempts WHERE user_id IN "
                "(SELECT id FROM users WHERE email IN ('test_p3d_user_a@example.com', 'test_p3d_user_b@example.com'))"
            )
        )
        self.db.execute(
            text(
                "DELETE FROM analyses WHERE user_id IN "
                "(SELECT id FROM users WHERE email IN ('test_p3d_user_a@example.com', 'test_p3d_user_b@example.com'))"
            )
        )
        self.db.execute(
            text(
                "DELETE FROM jobs WHERE user_id IN "
                "(SELECT id FROM users WHERE email IN ('test_p3d_user_a@example.com', 'test_p3d_user_b@example.com'))"
            )
        )
        self.db.execute(
            text(
                "DELETE FROM cvs WHERE user_id IN "
                "(SELECT id FROM users WHERE email IN ('test_p3d_user_a@example.com', 'test_p3d_user_b@example.com'))"
            )
        )
        self.db.execute(
            text(
                "DELETE FROM users WHERE email IN ('test_p3d_user_a@example.com', 'test_p3d_user_b@example.com')"
            )
        )
        self.db.commit()

        # Create user A
        self.client.post(
            "/users",
            json={
                "name": "Candidate A",
                "email": "test_p3d_user_a@example.com",
                "password": "Password123!",
            },
        )
        login_a = self.client.post(
            "/login",
            data={
                "username": "test_p3d_user_a@example.com",
                "password": "Password123!",
            },
        ).json()
        self.token_a = login_a["access_token"]
        self.headers_a = {"Authorization": f"Bearer {self.token_a}"}
        self.user_a_id = self.db.execute(
            text("SELECT id FROM users WHERE email = 'test_p3d_user_a@example.com'")
        ).scalar()

        # Create user B
        self.client.post(
            "/users",
            json={
                "name": "Candidate B",
                "email": "test_p3d_user_b@example.com",
                "password": "Password123!",
            },
        )
        login_b = self.client.post(
            "/login",
            data={
                "username": "test_p3d_user_b@example.com",
                "password": "Password123!",
            },
        ).json()
        self.token_b = login_b["access_token"]
        self.headers_b = {"Authorization": f"Bearer {self.token_b}"}
        self.user_b_id = self.db.execute(
            text("SELECT id FROM users WHERE email = 'test_p3d_user_b@example.com'")
        ).scalar()

        # Setup analysis session for user A
        cv = CV(user_id=self.user_a_id, file_name="resume.pdf", file_path="uploads/resume.pdf")
        self.db.add(cv)
        self.db.flush()

        job = Job(
            user_id=self.user_a_id,
            title="Backend Engineer",
            company="Acme Corp",
            description='[{"skill": "Python", "level": "intermediate", "importance": "required"}]',
        )
        self.db.add(job)
        self.db.flush()

        self.analysis = Analysis(
            user_id=self.user_a_id,
            job_id=job.id,
            cv_id=cv.id,
            overall_score=75.0,
            raw_analysis_data='[{"skill": "Python", "required_level": "intermediate", "importance": "required", "cv_level": "basic", "cv_match_status": "Match", "evidence": "Python scripting experience"}]',
        )
        self.db.add(self.analysis)
        self.db.commit()
        self.analysis_id = self.analysis.id

    def tearDown(self):
        from app.rate_limiter import limiter
        limiter.enabled = getattr(self, "_limiter_was_enabled", True)
        self.db.close()

    def _complete_attempt(self, attempt_id: int, user_id: int, score_pct: float, assessed_level: str):
        """Helper to answer and complete an attempt with a desired score across basic, intermediate, and advanced."""
        b_qs = self.db.query(AssessmentQuestion).filter(AssessmentQuestion.skill == "Python", AssessmentQuestion.level == "basic", AssessmentQuestion.is_active == True).limit(5).all()
        i_qs = self.db.query(AssessmentQuestion).filter(AssessmentQuestion.skill == "Python", AssessmentQuestion.level == "intermediate", AssessmentQuestion.is_active == True).limit(5).all()
        a_qs = self.db.query(AssessmentQuestion).filter(AssessmentQuestion.skill == "Python", AssessmentQuestion.level == "advanced", AssessmentQuestion.is_active == True).limit(5).all()

        all_qs = b_qs + i_qs + a_qs
        correct_to_give = round(len(all_qs) * score_pct)

        for idx, q in enumerate(all_qs):
            ans_letter = q.correct_answer if idx < correct_to_give else ("A" if q.correct_answer != "A" else "B")
            is_corr = (ans_letter == q.correct_answer)
            ans = AssessmentAnswer(
                attempt_id=attempt_id,
                question_id=q.id,
                selected_answer=ans_letter,
                is_correct=is_corr,
                time_taken=12.5,
            )
            self.db.add(ans)

        att = self.db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
        assert att is not None
        att.completed_at = datetime.now(timezone.utc)
        att.assessed_level = assessed_level
        self.db.commit()

    def test_01_no_completed_attempts(self):
        """When no attempts exist, centralized selection returns None, and views show unassessed state."""
        att = select_eligible_assessment_attempt(
            db=self.db,
            skill="Python",
            user_id=self.user_a_id,
            analysis_id=self.analysis_id,
        )
        self.assertIsNone(att)

        res = get_assessment_result_for_skill(
            db=self.db,
            skill="Python",
            user_id=self.user_a_id,
            analysis_id=self.analysis_id,
        )
        self.assertIsNone(res)

        # CV combine session returns unassessed fields
        cv_result = {
            "matched_skills": [{"skill": "Python", "required_level": "intermediate", "cv_match_status": "Match"}],
            "missing_skills": [],
            "skills": [{"skill": "Python", "required_level": "intermediate", "cv_match_status": "Match"}],
            "score_data": {"score": 50},
        }
        combined = combine_cv_and_assessment(
            cv_matching_result=cv_result,
            db_or_assessments=self.db,
            user_id=self.user_a_id,
            analysis_id=self.analysis_id,
        )
        skill_entry = combined["skills"][0]
        self.assertIsNone(skill_entry["assessed_level"])
        self.assertIsNone(skill_entry["total_score"])
        self.assertIsNone(skill_entry["attempt_id"])
        self.assertIsNone(skill_entry["completed_at"])
        self.assertTrue(combined["is_preliminary"])

    def test_02_first_completed_attempt(self):
        """First completed attempt is selected by Skill Match, report, and review with consistent data."""
        # Start and complete attempt 1 with score 40% (basic)
        start_res = self.client.post(
            "/assessment/start",
            json={
                "skill": "Python",
                "required_level": "intermediate",
                "analysis_id": self.analysis_id,
                "user_id": self.user_a_id,
            },
            headers=self.headers_a,
        )
        self.assertEqual(start_res.status_code, 201)
        att1_id = start_res.json()["attempt_id"]

        self._complete_attempt(att1_id, self.user_a_id, score_pct=0.40, assessed_level="basic")

        # 1. Centralized selection selects attempt 1
        att = select_eligible_assessment_attempt(
            db=self.db,
            skill="Python",
            user_id=self.user_a_id,
            analysis_id=self.analysis_id,
        )
        self.assertIsNotNone(att)
        self.assertEqual(att.id, att1_id)

        # 2. get_assessment_result_for_skill returns attempt 1 ID, score, and completion timestamp
        res = get_assessment_result_for_skill(
            db=self.db,
            skill="Python",
            user_id=self.user_a_id,
            analysis_id=self.analysis_id,
        )
        self.assertEqual(res["attempt_id"], att1_id)
        self.assertEqual(res["assessed_level"], "basic")
        self.assertIsNotNone(res["completed_at"])

        # 3. GET /cv/sessions/{analysis_id} returns attempt 1 ID on the skill
        sess_res = self.client.get(f"/cv/sessions/{self.analysis_id}", headers=self.headers_a)
        self.assertEqual(sess_res.status_code, 200)
        sess_skill = sess_res.json()["skills"][0]
        self.assertEqual(sess_skill["attempt_id"], att1_id)
        self.assertEqual(sess_skill["assessed_level"], "basic")
        self.assertIsNotNone(sess_skill["completed_at"])

        # 4. Review answers for attempt 1 opens exact attempt
        rev = self.client.get(f"/assessment/{att1_id}/review", headers=self.headers_a)
        self.assertEqual(rev.status_code, 200)
        self.assertEqual(rev.json()["attempt_id"], att1_id)
        self.assertEqual(rev.json()["assessed_level"], "basic")

    def test_03_active_retake_does_not_replace_completed_attempt(self):
        """An active (in-progress) retake must not replace the existing completed attempt."""
        # Setup completed attempt 1
        att1 = AssessmentAttempt(
            user_id=self.user_a_id,
            analysis_id=self.analysis_id,
            skill="Python",
            required_level="intermediate",
            assessed_level="basic",
            completed_at=datetime.now(timezone.utc),
        )
        self.db.add(att1)
        self.db.commit()
        att1_id = att1.id

        # Now user starts an active retake (attempt 2), which is in-progress (completed_at is None)
        start_res = self.client.post(
            "/assessment/start",
            json={
                "skill": "Python",
                "required_level": "intermediate",
                "analysis_id": self.analysis_id,
                "user_id": self.user_a_id,
            },
            headers=self.headers_a,
        )
        self.assertEqual(start_res.status_code, 201)
        att2_id = start_res.json()["attempt_id"]
        self.assertNotEqual(att1_id, att2_id)

        # Verify attempt 2 is in-progress
        att2_db = self.db.query(AssessmentAttempt).filter(AssessmentAttempt.id == att2_id).first()
        self.assertIsNone(att2_db.completed_at)

        # Centralized attempt selection MUST still return attempt 1
        selected = select_eligible_assessment_attempt(
            db=self.db,
            skill="Python",
            user_id=self.user_a_id,
            analysis_id=self.analysis_id,
        )
        self.assertIsNotNone(selected)
        self.assertEqual(selected.id, att1_id, "In-progress retake must NOT replace completed attempt!")

        # get_assessment_result_for_skill returns attempt 1
        res = get_assessment_result_for_skill(
            db=self.db,
            skill="Python",
            user_id=self.user_a_id,
            analysis_id=self.analysis_id,
        )
        self.assertEqual(res["attempt_id"], att1_id)

        # Session endpoint returns attempt 1
        sess_res = self.client.get(f"/cv/sessions/{self.analysis_id}", headers=self.headers_a)
        self.assertEqual(sess_res.json()["skills"][0]["attempt_id"], att1_id)

    def test_04_completed_retake_updates_all_views_consistently(self):
        """When retake is completed with a different result, all report views agree on the new attempt."""
        # 1. Complete attempt 1 (Score: 40%, basic)
        start1 = self.client.post(
            "/assessment/start",
            json={"skill": "Python", "required_level": "intermediate", "analysis_id": self.analysis_id, "user_id": self.user_a_id},
            headers=self.headers_a,
        )
        att1_id = start1.json()["attempt_id"]
        self._complete_attempt(att1_id, self.user_a_id, score_pct=0.40, assessed_level="basic")

        # 2. Retake Python (attempt 2) and complete with Score: 100% (advanced)
        start2 = self.client.post(
            "/assessment/start",
            json={"skill": "Python", "required_level": "intermediate", "analysis_id": self.analysis_id, "user_id": self.user_a_id},
            headers=self.headers_a,
        )
        att2_id = start2.json()["attempt_id"]
        self._complete_attempt(att2_id, self.user_a_id, score_pct=1.0, assessed_level="advanced")

        # 3. Centralized selection selects attempt 2
        selected = select_eligible_assessment_attempt(
            db=self.db,
            skill="Python",
            user_id=self.user_a_id,
            analysis_id=self.analysis_id,
        )
        self.assertEqual(selected.id, att2_id)

        # 4. Result by skill returns attempt 2 with advanced level
        res_by_skill = self.client.get(f"/assessment/result/Python?analysis_id={self.analysis_id}", headers=self.headers_a)
        self.assertEqual(res_by_skill.status_code, 200)
        self.assertEqual(res_by_skill.json()["attempt_id"], att2_id)
        self.assertEqual(res_by_skill.json()["assessed_level"], "advanced")
        self.assertEqual(res_by_skill.json()["skill_recommendation"], "Mastered")

        # 5. Session endpoint (/cv/sessions/{analysis_id}) agrees on attempt 2
        sess_res = self.client.get(f"/cv/sessions/{self.analysis_id}", headers=self.headers_a)
        skill_data = sess_res.json()["skills"][0]
        self.assertEqual(skill_data["attempt_id"], att2_id)
        self.assertEqual(skill_data["assessed_level"], "advanced")
        self.assertEqual(skill_data["skill_recommendation"], "Mastered")
        self.assertEqual(sess_res.json()["assessment_view_mode"], "latest_verified")

        # 6. Session list endpoint (/cv/sessions) also agrees
        list_res = self.client.get("/cv/sessions", headers=self.headers_a)
        sess_item = [s for s in list_res.json()["sessions"] if s["analysis_id"] == self.analysis_id][0]
        self.assertEqual(sess_item["skills"][0]["attempt_id"], att2_id)
        self.assertEqual(sess_item["assessment_view_mode"], "latest_verified")

        # 7. Aggregation uses attempt 2 data and reflects verified readiness
        agg_res = self.client.post(
            "/assessment/aggregate",
            json={"skills": [skill_data]},
            headers=self.headers_a,
        )
        self.assertEqual(agg_res.status_code, 200)
        self.assertEqual(agg_res.json()["requirements_verified_assessment"], 1)
        self.assertEqual(agg_res.json()["confirmed_gaps_count"], 0)

        # 8. Revision weaknesses endpoint scoped to this analysis reflects attempt 2 (no weak topics for Python)
        weak_res = self.client.get(f"/assessment/revision/weaknesses?analysis_id={self.analysis_id}", headers=self.headers_a)
        self.assertEqual(weak_res.status_code, 200)
        py_weak = [wt for wt in weak_res.json()["weak_topics"] if wt["skill"].lower() == "python"]
        self.assertEqual(len(py_weak), 0, "Mastered retake should not produce weak topics in the report!")

    def test_05_older_attempt_still_reviewable_on_its_own(self):
        """Candidate can review the older attempt by exact attempt ID with its own answers and score."""
        # Complete attempt 1 (score: 40%, basic)
        start1 = self.client.post(
            "/assessment/start",
            json={"skill": "Python", "required_level": "intermediate", "analysis_id": self.analysis_id, "user_id": self.user_a_id},
            headers=self.headers_a,
        )
        att1_id = start1.json()["attempt_id"]
        self._complete_attempt(att1_id, self.user_a_id, score_pct=0.40, assessed_level="basic")

        # Complete attempt 2 (score: 100%, advanced)
        start2 = self.client.post(
            "/assessment/start",
            json={"skill": "Python", "required_level": "intermediate", "analysis_id": self.analysis_id, "user_id": self.user_a_id},
            headers=self.headers_a,
        )
        att2_id = start2.json()["attempt_id"]
        self._complete_attempt(att2_id, self.user_a_id, score_pct=1.0, assessed_level="advanced")

        # Query attempt 1 review by its exact ID
        rev1 = self.client.get(f"/assessment/{att1_id}/review", headers=self.headers_a)
        self.assertEqual(rev1.status_code, 200)
        data1 = rev1.json()
        self.assertEqual(data1["attempt_id"], att1_id)
        self.assertEqual(data1["assessed_level"], "basic")
        self.assertEqual(data1["correct_count"], 6)
        self.assertEqual(data1["incorrect_count"], 9)

        # Query attempt 2 review by its exact ID
        rev2 = self.client.get(f"/assessment/{att2_id}/review", headers=self.headers_a)
        self.assertEqual(rev2.status_code, 200)
        data2 = rev2.json()
        self.assertEqual(data2["attempt_id"], att2_id)
        self.assertEqual(data2["assessed_level"], "advanced")
        self.assertEqual(data2["correct_count"], 15)
        self.assertEqual(data2["incorrect_count"], 0)

        # Query attempt 1 result by its exact ID
        res1 = self.client.get(f"/assessment/{att1_id}/result", headers=self.headers_a)
        self.assertEqual(res1.status_code, 200)
        self.assertEqual(res1.json()["attempt_id"], att1_id)
        self.assertEqual(res1.json()["assessed_level"], "basic")

        # Query attempt 2 result by its exact ID
        res2 = self.client.get(f"/assessment/{att2_id}/result", headers=self.headers_a)
        self.assertEqual(res2.status_code, 200)
        self.assertEqual(res2.json()["attempt_id"], att2_id)
        self.assertEqual(res2.json()["assessed_level"], "advanced")

    def test_06_unauthorized_user_cannot_access_attempt(self):
        """User B cannot fetch User A's attempt review, result, or analysis session by changing IDs."""
        # Create attempt for user A
        start1 = self.client.post(
            "/assessment/start",
            json={"skill": "Python", "required_level": "intermediate", "analysis_id": self.analysis_id, "user_id": self.user_a_id},
            headers=self.headers_a,
        )
        att1_id = start1.json()["attempt_id"]
        self._complete_attempt(att1_id, self.user_a_id, score_pct=0.80, assessed_level="intermediate")

        # User B attempts to access User A's review -> 403 Forbidden
        rev_b = self.client.get(f"/assessment/{att1_id}/review", headers=self.headers_b)
        self.assertEqual(rev_b.status_code, 403)

        # User B attempts to access User A's result -> 403 Forbidden
        res_b = self.client.get(f"/assessment/{att1_id}/result", headers=self.headers_b)
        self.assertEqual(res_b.status_code, 403)

        # User B attempts to access User A's analysis session -> 404 Not Found (user scoped)
        sess_b = self.client.get(f"/cv/sessions/{self.analysis_id}", headers=self.headers_b)
        self.assertEqual(sess_b.status_code, 404)

        # User B attempts to query revision weaknesses with User A's analysis_id -> 404 Not Found
        weak_b = self.client.get(f"/assessment/revision/weaknesses?analysis_id={self.analysis_id}", headers=self.headers_b)
        self.assertEqual(weak_b.status_code, 404)

    def test_07_stable_tie_break_with_identical_timestamps(self):
        """When multiple attempts share identical completed_at timestamps, tie-break by id.desc() is stable."""
        shared_time = datetime(2026, 11, 7, 2, 0, 0, tzinfo=timezone.utc)
        att_low = AssessmentAttempt(
            user_id=self.user_a_id,
            analysis_id=self.analysis_id,
            skill="Python",
            required_level="intermediate",
            assessed_level="basic",
            completed_at=shared_time,
        )
        self.db.add(att_low)
        self.db.commit()

        att_high = AssessmentAttempt(
            user_id=self.user_a_id,
            analysis_id=self.analysis_id,
            skill="Python",
            required_level="intermediate",
            assessed_level="advanced",
            completed_at=shared_time,
        )
        self.db.add(att_high)
        self.db.commit()

        self.assertGreater(att_high.id, att_low.id)

        selected = select_eligible_assessment_attempt(
            db=self.db,
            skill="Python",
            user_id=self.user_a_id,
            analysis_id=self.analysis_id,
        )
        self.assertEqual(selected.id, att_high.id, "Tie-break must pick higher id deterministically!")

    def test_08_unfinished_retake_preserves_completed_result_in_all_report_endpoints(self):
        """Unfinished retake leaves the previous completed attempt visible across session, list, and skill result."""
        # 1. Complete attempt 1 (Score: 40%, basic)
        start1 = self.client.post(
            "/assessment/start",
            json={"skill": "Python", "required_level": "intermediate", "analysis_id": self.analysis_id, "user_id": self.user_a_id},
            headers=self.headers_a,
        )
        att1_id = start1.json()["attempt_id"]
        self._complete_attempt(att1_id, self.user_a_id, score_pct=0.40, assessed_level="basic")

        # Verify completed attempt 1 is visible
        sess_before = self.client.get(f"/cv/sessions/{self.analysis_id}", headers=self.headers_a)
        self.assertEqual(sess_before.status_code, 200)
        self.assertEqual(sess_before.json()["skills"][0]["attempt_id"], att1_id)
        self.assertEqual(sess_before.json()["skills"][0]["assessed_level"], "basic")

        # 2. Start an unfinished retake (attempt 2), submit 1 question, but leave unfinished
        start2 = self.client.post(
            "/assessment/start",
            json={"skill": "Python", "required_level": "intermediate", "analysis_id": self.analysis_id, "user_id": self.user_a_id},
            headers=self.headers_a,
        )
        att2_id = start2.json()["attempt_id"]
        q_id = start2.json()["questions"][0]["id"]
        # Submit single answer so attempt 2 is in-progress
        self.client.post(
            "/assessment/answer",
            json={"attempt_id": att2_id, "question_id": q_id, "selected_answer": "A", "time_taken": 10},
            headers=self.headers_a,
        )
        # Attempt 2 is NOT completed
        att2_db = self.db.query(AssessmentAttempt).filter(AssessmentAttempt.id == att2_id).first()
        self.assertIsNone(att2_db.completed_at)

        # 3. Candidate returns to dashboard / report: GET /cv/sessions/{analysis_id} must STILL show attempt 1
        sess_after = self.client.get(f"/cv/sessions/{self.analysis_id}", headers=self.headers_a)
        self.assertEqual(sess_after.status_code, 200)
        py_skill = sess_after.json()["skills"][0]
        self.assertEqual(py_skill["attempt_id"], att1_id, "Unfinished retake must NOT hide completed attempt!")
        self.assertEqual(py_skill["assessed_level"], "basic")
        self.assertEqual(py_skill["total_score"], sess_before.json()["skills"][0]["total_score"])

        # 4. History list GET /cv/sessions must STILL show attempt 1
        list_res = self.client.get("/cv/sessions", headers=self.headers_a)
        sess_item = [s for s in list_res.json()["sessions"] if s["analysis_id"] == self.analysis_id][0]
        self.assertEqual(sess_item["skills"][0]["attempt_id"], att1_id)

        # 5. GET /assessment/result/Python must STILL show attempt 1
        res_skill = self.client.get(f"/assessment/result/Python?analysis_id={self.analysis_id}", headers=self.headers_a)
        self.assertEqual(res_skill.status_code, 200)
        self.assertEqual(res_skill.json()["attempt_id"], att1_id)
        self.assertEqual(res_skill.json()["assessed_level"], "basic")

    def test_09_assessment_completion_updates_session_and_aggregation_automatically(self):
        """Completing an assessment automatically updates session detail, score aggregation, and review."""
        # 1. Start and complete attempt for Python (score: 100%, advanced)
        start = self.client.post(
            "/assessment/start",
            json={"skill": "Python", "required_level": "intermediate", "analysis_id": self.analysis_id, "user_id": self.user_a_id},
            headers=self.headers_a,
        )
        att_id = start.json()["attempt_id"]
        self._complete_attempt(att_id, self.user_a_id, score_pct=1.0, assessed_level="advanced")

        # 2. Call complete endpoint
        comp_res = self.client.post(f"/assessment/{att_id}/complete", headers=self.headers_a)
        self.assertEqual(comp_res.status_code, 200)
        self.assertEqual(comp_res.json()["status"], "completed")

        # 3. GET /cv/sessions/{analysis_id} automatically returns the completed attempt and updated verdict
        sess_res = self.client.get(f"/cv/sessions/{self.analysis_id}", headers=self.headers_a)
        self.assertEqual(sess_res.status_code, 200)
        py_skill = sess_res.json()["skills"][0]
        self.assertEqual(py_skill["attempt_id"], att_id)
        self.assertEqual(py_skill["assessed_level"], "advanced")
        self.assertEqual(py_skill["skill_recommendation"], "Mastered")
        self.assertFalse(py_skill["is_weakness"])

        # 4. Aggregation returns verified assessment without needing manual intervention
        agg_res = self.client.post("/assessment/aggregate", json={"skills": [py_skill]}, headers=self.headers_a)
        self.assertEqual(agg_res.status_code, 200)
        self.assertEqual(agg_res.json()["requirements_verified_assessment"], 1)
        self.assertEqual(agg_res.json()["confirmed_gaps_count"], 0)


if __name__ == "__main__":
    unittest.main()
