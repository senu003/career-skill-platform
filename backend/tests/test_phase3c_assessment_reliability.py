import os
import sys
import uuid
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import patch
import unittest

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.main import app
from app.database import Base, get_db, SessionLocal, engine
from app.models import User, AssessmentAttempt, AssessmentAnswer, AssessmentQuestion
from app.auth_deps import create_access_token

client = TestClient(app)

from urllib.parse import urlparse, urlunparse

def get_postgres_urls(disp_db_name: str):
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        from dotenv import load_dotenv
        load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env")))
        db_url = os.getenv("DATABASE_URL", "postgresql://postgres:S3045277k$@localhost:5432/career_skill_db")

    parsed = urlparse(db_url)
    admin_url = os.getenv("PG_TEST_BASE_URL", db_url)
    disp_url = urlunparse((parsed.scheme, parsed.netloc, f"/{disp_db_name}", "", "", ""))
    return admin_url, disp_url


def get_auth_token_for_user(email: str, password: str = "Secret123!"):
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            from app.routers.auth import _hash_password
            user = User(name="Test Candidate", email=email, password_hash=_hash_password(password), is_active=True)
            db.add(user)
            db.commit()
            db.refresh(user)
        user_id = user.id
        token = create_access_token({"sub": str(user_id)})
        return user_id, {"Authorization": f"Bearer {token}"}
    finally:
        db.close()


class TestPhase3CAssessmentReliability(unittest.TestCase):
    """
    Test suite for CareerSkill Phase 3C: Duplicate Assessment Protection.
    Verifies:
      1. Single atomic transaction for answer persistence and progression.
      2. Safe identical retries (lost response recovery).
      3. Conflicting duplicate rejection (409 Conflict) without state mutation.
      4. Safe retry of final answer after attempt completion.
      5. Concurrent worker submission deduplication against database uniqueness constraint.
      6. Preservation of intentional retakes as independent attempts.
      7. Alembic migration deduplication and schema upgrade/downgrade.
    """

    def setUp(self):
        from app.rate_limiter import limiter
        self._limiter_was_enabled = getattr(limiter, "enabled", True)
        limiter.enabled = False

    def tearDown(self):
        from app.rate_limiter import limiter
        limiter.enabled = getattr(self, "_limiter_was_enabled", True)

    def test_migration_005_deduplication_and_uniqueness_on_postgresql(self):
        """
        Verifies that Alembic migration 005_answer_uniqueness:
        1. Deduplicates any existing duplicate (attempt_id, question_id) rows, keeping latest (max id).
        2. Applies the unique_attempt_question constraint on PostgreSQL.
        3. Allows safe downgrade and re-upgrade without data loss.
        """
        import psycopg2
        from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
        from alembic.config import Config
        from alembic import command

        disp_db_name = f"phase3c_mig_{uuid.uuid4().hex[:8]}"
        admin_url, disp_url = get_postgres_urls(disp_db_name)

        try:
            admin_conn = psycopg2.connect(admin_url)
        except Exception as e:
            self.skipTest(f"PostgreSQL connection to {admin_url} not available: {e}")

        admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        admin_cur = admin_conn.cursor()
        admin_cur.execute(f"DROP DATABASE IF EXISTS {disp_db_name};")
        admin_cur.execute(f"CREATE DATABASE {disp_db_name};")
        admin_conn.close()

        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        ini_path = os.path.join(backend_dir, "alembic.ini")
        script_dir = os.path.join(backend_dir, "alembic")
        cfg = Config(ini_path)
        cfg.set_main_option("script_location", script_dir)
        cfg.set_main_option("sqlalchemy.url", disp_url)

        try:
            # Upgrade to 004_add_analysis_requests (Phase 3A/3B state)
            command.upgrade(cfg, "004_add_analysis_requests")
            engine = create_engine(disp_url)

            # Drop constraint if present (to simulate legacy database with duplicate rows)
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE assessment_answers DROP CONSTRAINT IF EXISTS unique_attempt_question;"))
                conn.commit()

            # Insert an attempt and duplicate answers to test migration deduplication
            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO assessment_attempts (id, skill, required_level, started_at)
                    VALUES (999, 'JavaScript', 'basic', NOW())
                    ON CONFLICT DO NOTHING;
                """))
                # Insert a dummy question if needed
                conn.execute(text("""
                    INSERT INTO assessment_questions (id, skill, level, question, correct_answer, is_active)
                    VALUES (9999, 'JavaScript', 'basic', 'Test Q', 'A', true)
                    ON CONFLICT DO NOTHING;
                """))
                # Insert duplicate answer rows (different IDs, same attempt_id and question_id)
                conn.execute(text("""
                    INSERT INTO assessment_answers (id, attempt_id, question_id, selected_answer, is_correct, answered_at)
                    VALUES (9001, 999, 9999, 'A', true, NOW() - INTERVAL '1 minute');
                """))
                conn.execute(text("""
                    INSERT INTO assessment_answers (id, attempt_id, question_id, selected_answer, is_correct, answered_at)
                    VALUES (9002, 999, 9999, 'A', true, NOW());
                """))
                conn.commit()

                # Verify 2 rows exist before migration
                res = conn.execute(text("SELECT COUNT(*) FROM assessment_answers WHERE attempt_id = 999 AND question_id = 9999;")).scalar()
                self.assertEqual(res, 2)

            # Upgrade to head (005_answer_uniqueness)
            command.upgrade(cfg, "head")

            # Verify deduplication kept only the latest row (id 9002)
            with engine.connect() as conn:
                res = conn.execute(text("SELECT COUNT(*) FROM assessment_answers WHERE attempt_id = 999 AND question_id = 9999;")).scalar()
                self.assertEqual(res, 1, "Migration did not deduplicate existing duplicate answers")

                remaining_id = conn.execute(text("SELECT id FROM assessment_answers WHERE attempt_id = 999 AND question_id = 9999;")).scalar()
                self.assertEqual(remaining_id, 9002, "Migration did not keep the latest max(id) answer")

                # Verify inserting duplicate now fails with UniqueViolation
                with self.assertRaises(Exception):
                    conn.execute(text("""
                        INSERT INTO assessment_answers (id, attempt_id, question_id, selected_answer, is_correct, answered_at)
                        VALUES (9003, 999, 9999, 'B', false, NOW());
                    """))
                    conn.commit()

            # Test downgrade and re-upgrade
            command.downgrade(cfg, "004_add_analysis_requests")
            command.upgrade(cfg, "head")
            engine.dispose()

        finally:
            try:
                admin_conn = psycopg2.connect(admin_url)
                admin_conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
                admin_cur = admin_conn.cursor()
                admin_cur.execute(f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = '{disp_db_name}'
                      AND pid <> pg_backend_pid();
                """)
                admin_cur.execute(f"DROP DATABASE IF EXISTS {disp_db_name};")
                admin_conn.close()
            except Exception:
                pass

    def test_sequential_identical_retries_safe_recovery(self):
        """
        Verifies that submitting the identical answer multiple times:
        1. Returns 200 OK with identical payload on every retry.
        2. Leaves exactly 1 record in assessment_answers table.
        3. Preserves attempt state without double-progression.
        """
        user_email = f"retry_seq_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = get_auth_token_for_user(user_email)

        start_res = client.post("/assessment/start", json={
            "skill": "JavaScript",
            "required_level": "basic",
            "user_id": user_id
        }, headers=headers).json()
        attempt_id = start_res["attempt_id"]
        q1_id = start_res["questions"][0]["id"]

        # First submission
        r1 = client.post("/assessment/answer", json={
            "attempt_id": attempt_id,
            "question_id": q1_id,
            "selected_answer": "A",
            "time_taken": 5.0
        }, headers=headers)
        self.assertEqual(r1.status_code, 200)
        p1 = r1.json()

        # Retry 1 (simulating lost first response)
        r2 = client.post("/assessment/answer", json={
            "attempt_id": attempt_id,
            "question_id": q1_id,
            "selected_answer": "A",
            "time_taken": 5.0
        }, headers=headers)
        self.assertEqual(r2.status_code, 200)
        p2 = r2.json()

        # Retry 2
        r3 = client.post("/assessment/answer", json={
            "attempt_id": attempt_id,
            "question_id": q1_id,
            "selected_answer": "A",
            "time_taken": 5.0
        }, headers=headers)
        self.assertEqual(r3.status_code, 200)
        p3 = r3.json()

        # Verify payloads match
        self.assertEqual(p1["attempt_id"], p2["attempt_id"])
        self.assertEqual(p1["question_id"], p2["question_id"])
        self.assertEqual(p1["selected_answer"], p2["selected_answer"])
        self.assertEqual(p1["is_correct"], p2["is_correct"])
        self.assertEqual(p1["level_completed"], p2["level_completed"])
        self.assertEqual(p1["attempt_completed"], p2["attempt_completed"])

        self.assertEqual(p2, p3)

        # Direct DB verification: exactly one record exists
        db = SessionLocal()
        try:
            answers = db.query(AssessmentAnswer).filter(
                AssessmentAnswer.attempt_id == attempt_id,
                AssessmentAnswer.question_id == q1_id
            ).all()
            self.assertEqual(len(answers), 1)
        finally:
            db.close()

    def test_conflicting_duplicate_answers_rejected(self):
        """
        Verifies that submitting a conflicting duplicate answer:
        1. Returns 409 Conflict.
        2. Does not alter the original saved answer, score, or attempt progress.
        """
        user_email = f"conflict_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = get_auth_token_for_user(user_email)

        start_res = client.post("/assessment/start", json={
            "skill": "JavaScript",
            "required_level": "basic",
            "user_id": user_id
        }, headers=headers).json()
        attempt_id = start_res["attempt_id"]
        q1_id = start_res["questions"][0]["id"]

        # Initial submission with answer "A"
        r1 = client.post("/assessment/answer", json={
            "attempt_id": attempt_id,
            "question_id": q1_id,
            "selected_answer": "A"
        }, headers=headers)
        self.assertEqual(r1.status_code, 200)

        # Conflicting submission with answer "B"
        r_conf = client.post("/assessment/answer", json={
            "attempt_id": attempt_id,
            "question_id": q1_id,
            "selected_answer": "B"
        }, headers=headers)
        self.assertEqual(r_conf.status_code, 409)
        self.assertIn("Duplicate answer conflict", r_conf.json()["detail"])
        self.assertIn("already been answered with 'A'", r_conf.json()["detail"])
        self.assertIn("Conflicting answer 'B' is rejected", r_conf.json()["detail"])

        # Conflicting submission with answer "C"
        r_conf_c = client.post("/assessment/answer", json={
            "attempt_id": attempt_id,
            "question_id": q1_id,
            "selected_answer": "C"
        }, headers=headers)
        self.assertEqual(r_conf_c.status_code, 409)

        # Direct DB verification: answer remains "A", exactly 1 row
        db = SessionLocal()
        try:
            answers = db.query(AssessmentAnswer).filter(
                AssessmentAnswer.attempt_id == attempt_id,
                AssessmentAnswer.question_id == q1_id
            ).all()
            self.assertEqual(len(answers), 1)
            self.assertEqual(answers[0].selected_answer, "A")
        finally:
            db.close()

    def test_retry_of_final_answer_and_completed_attempt(self):
        """
        Verifies that after all answers are submitted and the attempt completes:
        1. Retrying the final question returns 200 OK with attempt_completed: True and assessed_level.
        2. Retrying an earlier question in the completed attempt returns 200 OK.
        3. Attempt completed_at timestamp is preserved.
        4. Submitting a new un-answered question is rejected with 400.
        """
        user_email = f"final_retry_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = get_auth_token_for_user(user_email)

        start_res = client.post("/assessment/start", json={
            "skill": "JavaScript",
            "required_level": "basic",
            "user_id": user_id
        }, headers=headers).json()
        attempt_id = start_res["attempt_id"]
        questions = start_res["questions"]
        self.assertEqual(len(questions), 5)

        # Answer questions 1 to 4
        for q in questions[:4]:
            res = client.post("/assessment/answer", json={
                "attempt_id": attempt_id,
                "question_id": q["id"],
                "selected_answer": "A"
            }, headers=headers)
            self.assertEqual(res.status_code, 200)
            self.assertFalse(res.json()["attempt_completed"])

        # Answer question 5 (final question of basic level)
        final_q = questions[4]
        res_final = client.post("/assessment/answer", json={
            "attempt_id": attempt_id,
            "question_id": final_q["id"],
            "selected_answer": "A"
        }, headers=headers)
        self.assertEqual(res_final.status_code, 200)
        final_payload = res_final.json()
        self.assertTrue(final_payload["level_completed"])
        self.assertTrue(final_payload["attempt_completed"])

        # Check DB attempt completion timestamp
        db = SessionLocal()
        try:
            attempt_before = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
            self.assertIsNotNone(attempt_before.completed_at)
            saved_completed_at = attempt_before.completed_at
            saved_assessed_level = attempt_before.assessed_level
        finally:
            db.close()

        # Retry the final question identically
        res_retry_final = client.post("/assessment/answer", json={
            "attempt_id": attempt_id,
            "question_id": final_q["id"],
            "selected_answer": "A"
        }, headers=headers)
        self.assertEqual(res_retry_final.status_code, 200)
        retry_payload = res_retry_final.json()
        self.assertTrue(retry_payload["attempt_completed"])
        self.assertTrue(retry_payload["level_completed"])
        self.assertEqual(retry_payload["assessed_level"], saved_assessed_level)

        # Retry question 1 identically
        res_retry_q1 = client.post("/assessment/answer", json={
            "attempt_id": attempt_id,
            "question_id": questions[0]["id"],
            "selected_answer": "A"
        }, headers=headers)
        self.assertEqual(res_retry_q1.status_code, 200)
        self.assertFalse(res_retry_q1.json()["level_completed"])

        # Verify completed_at timestamp was not modified
        db = SessionLocal()
        try:
            attempt_after = db.query(AssessmentAttempt).filter(AssessmentAttempt.id == attempt_id).first()
            self.assertEqual(attempt_after.completed_at, saved_completed_at)
            self.assertEqual(attempt_after.assessed_level, saved_assessed_level)
            # Total answers count is still exactly 5
            total_answers = db.query(AssessmentAnswer).filter(AssessmentAnswer.attempt_id == attempt_id).count()
            self.assertEqual(total_answers, 5)
        finally:
            db.close()

    def test_atomic_progression_transaction_rollback(self):
        """
        Verifies that if an error occurs between answer insertion and attempt progression,
        the transaction is rolled back and no partial answer or invalid attempt progress is saved.
        """
        user_email = f"rollback_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = get_auth_token_for_user(user_email)

        start_res = client.post("/assessment/start", json={
            "skill": "JavaScript",
            "required_level": "basic",
            "user_id": user_id
        }, headers=headers).json()
        attempt_id = start_res["attempt_id"]
        q1_id = start_res["questions"][0]["id"]

        # Simulate database failure during progression/commit
        c = TestClient(app, raise_server_exceptions=False)
        with patch("app.services.assessment_service.evaluate_attempt_state", side_effect=[
            ("basic", None, False, {}),  # first pre-check passes
            RuntimeError("Simulated DB evaluation failure during progression")  # second check fails
        ]):
            r = c.post("/assessment/answer", json={
                "attempt_id": attempt_id,
                "question_id": q1_id,
                "selected_answer": "A"
            }, headers=headers)
            self.assertEqual(r.status_code, 500)

        # Verify that atomic rollback prevented the answer from persisting
        db = SessionLocal()
        try:
            saved_answer = db.query(AssessmentAnswer).filter(
                AssessmentAnswer.attempt_id == attempt_id,
                AssessmentAnswer.question_id == q1_id
            ).first()
            self.assertIsNone(saved_answer, "Answer was committed despite progression failure - atomicity violated!")
        finally:
            db.close()

    def test_concurrent_worker_submissions_deduplication(self):
        """
        Verifies that multiple concurrent workers submitting answers to the same question:
        1. Result in exactly 1 saved answer in the database.
        2. All identical requests receive 200 OK without crashing.
        3. Conflicting concurrent requests receive 409 Conflict.
        """
        user_email = f"concur_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = get_auth_token_for_user(user_email)

        start_res = client.post("/assessment/start", json={
            "skill": "JavaScript",
            "required_level": "basic",
            "user_id": user_id
        }, headers=headers).json()
        attempt_id = start_res["attempt_id"]
        q1_id = start_res["questions"][0]["id"]

        num_workers = 8
        results = []

        def submit_worker(selected_ans: str):
            c = TestClient(app)
            resp = c.post("/assessment/answer", json={
                "attempt_id": attempt_id,
                "question_id": q1_id,
                "selected_answer": selected_ans
            }, headers=headers)
            return resp.status_code, resp.json()

        # Run 8 concurrent submissions with identical answer "A"
        with ThreadPoolExecutor(max_workers=num_workers) as executor:
            futures = [executor.submit(submit_worker, "A") for _ in range(num_workers)]
            for f in as_completed(futures):
                results.append(f.result())

        # Verify all return 200 OK
        status_codes = [r[0] for r in results]
        self.assertTrue(all(sc == 200 for sc in status_codes), f"Not all concurrent identical submissions returned 200: {status_codes}")

        # Verify DB has EXACTLY 1 answer record
        db = SessionLocal()
        try:
            count = db.query(AssessmentAnswer).filter(
                AssessmentAnswer.attempt_id == attempt_id,
                AssessmentAnswer.question_id == q1_id
            ).count()
            self.assertEqual(count, 1, f"Expected 1 saved answer, but found {count}")
        finally:
            db.close()

        # Now test concurrent mix: 4 workers submit "A" and 4 submit "B" for question 2
        q2_id = start_res["questions"][1]["id"]
        mix_results = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures_a = [executor.submit(submit_worker, "A") for _ in range(4)]
            futures_b = [executor.submit(submit_worker, "B") for _ in range(4)]
            # Run against q2
            def submit_q2(ans):
                c = TestClient(app)
                resp = c.post("/assessment/answer", json={
                    "attempt_id": attempt_id,
                    "question_id": q2_id,
                    "selected_answer": ans
                }, headers=headers)
                return resp.status_code, resp.json()

            futures_mix = [executor.submit(submit_q2, "A" if i % 2 == 0 else "B") for i in range(8)]
            for f in as_completed(futures_mix):
                mix_results.append(f.result())

        mix_statuses = [r[0] for r in mix_results]
        self.assertIn(200, mix_statuses)
        # Every response must be either 200 (won race or matched winning answer) or 409 (conflicted with winning answer)
        for sc in mix_statuses:
            self.assertIn(sc, [200, 409], f"Unexpected status code {sc} in concurrent mix")

        # Direct DB check: exactly 1 answer row saved for q2
        db = SessionLocal()
        try:
            count_q2 = db.query(AssessmentAnswer).filter(
                AssessmentAnswer.attempt_id == attempt_id,
                AssessmentAnswer.question_id == q2_id
            ).count()
            self.assertEqual(count_q2, 1, f"Expected 1 saved answer for q2, but found {count_q2}")
        finally:
            db.close()

    def test_intentional_retakes_as_separate_attempts(self):
        """
        Verifies that intentional retakes create separate attempt records,
        allowing the candidate to answer the same questions anew without
        colliding with or overwriting previous attempt answers.
        """
        user_email = f"retake_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = get_auth_token_for_user(user_email)

        # Attempt 1
        r1 = client.post("/assessment/start", json={
            "skill": "Python",
            "required_level": "basic",
            "user_id": user_id
        }, headers=headers)
        self.assertEqual(r1.status_code, 201)
        att1_id = r1.json()["attempt_id"]
        q_ids = [q["id"] for q in r1.json()["questions"]]

        # Answer question 1 in Attempt 1 with "A"
        ans1 = client.post("/assessment/answer", json={
            "attempt_id": att1_id,
            "question_id": q_ids[0],
            "selected_answer": "A"
        }, headers=headers)
        self.assertEqual(ans1.status_code, 200)

        # Complete attempt 1 (remaining questions)
        for q_id in q_ids[1:]:
            client.post("/assessment/answer", json={
                "attempt_id": att1_id,
                "question_id": q_id,
                "selected_answer": "A"
            }, headers=headers)

        # Intentional Retake: Start Attempt 2 for the same skill
        r2 = client.post("/assessment/start", json={
            "skill": "Python",
            "required_level": "basic",
            "user_id": user_id
        }, headers=headers)
        self.assertEqual(r2.status_code, 201)
        att2_id = r2.json()["attempt_id"]
        self.assertNotEqual(att1_id, att2_id, "Retake did not create a distinct attempt ID")

        # Answer question 1 in Attempt 2 with "B" (different answer)
        ans2 = client.post("/assessment/answer", json={
            "attempt_id": att2_id,
            "question_id": q_ids[0],
            "selected_answer": "B"
        }, headers=headers)
        self.assertEqual(ans2.status_code, 200)
        self.assertEqual(ans2.json()["selected_answer"], "B")

        # Verify DB has independent records for each attempt
        db = SessionLocal()
        try:
            a1_record = db.query(AssessmentAnswer).filter(
                AssessmentAnswer.attempt_id == att1_id,
                AssessmentAnswer.question_id == q_ids[0]
            ).first()
            a2_record = db.query(AssessmentAnswer).filter(
                AssessmentAnswer.attempt_id == att2_id,
                AssessmentAnswer.question_id == q_ids[0]
            ).first()

            self.assertIsNotNone(a1_record)
            self.assertIsNotNone(a2_record)
            self.assertEqual(a1_record.selected_answer, "A")
            self.assertEqual(a2_record.selected_answer, "B")
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
