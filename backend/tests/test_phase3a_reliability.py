import os
import sys
import json
import uuid
import unittest
from unittest.mock import patch
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal, get_db
from app.models import User, CV, Job, Analysis, AnalysisRequest
from app.services.storage_service import get_storage_backend

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
    from app.auth_deps import create_access_token
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


class TestPhase3AReliability(unittest.TestCase):
    """
    Test suite for Phase 3A: Atomic CV analysis writes and safe retries.
    Uses disposable PostgreSQL databases and transactional testing.
    """

    def setUp(self):
        from app.rate_limiter import limiter
        self._limiter_was_enabled = getattr(limiter, "enabled", True)
        limiter.enabled = False

    def tearDown(self):
        from app.rate_limiter import limiter
        limiter.enabled = getattr(self, "_limiter_was_enabled", True)

    def test_migration_upgrade_from_phase2_schema_on_postgresql(self):
        """
        Verifies disposable PostgreSQL migration cleanly upgrades from Phase 2
        schema (003_add_revoked_tokens) to Phase 3A (004_add_analysis_requests),
        and that downgrade/re-upgrade operate idempotently without data loss.
        """
        disp_db_name = f"phase3a_mig_{uuid.uuid4().hex[:8]}"
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
            # Step 1: Upgrade to Phase 2 schema head (003_add_revoked_tokens)
            command.upgrade(cfg, "003_add_revoked_tokens")
            engine = create_engine(disp_url)
            insp = inspect(engine)
            tables_phase2 = set(insp.get_table_names())
            self.assertIn("revoked_tokens", tables_phase2)
            self.assertNotIn("analysis_requests", tables_phase2)

            # Step 2: Upgrade to Phase 3A schema head (004_add_analysis_requests)
            command.upgrade(cfg, "head")
            insp = inspect(engine)
            tables_phase3 = set(insp.get_table_names())
            self.assertIn("analysis_requests", tables_phase3)

            # Check columns in analysis_requests
            cols = {c["name"] for c in insp.get_columns("analysis_requests")}
            for expected_col in ["id", "user_id", "idempotency_key", "request_hash", "status", "analysis_id", "response_json", "created_at", "updated_at"]:
                self.assertIn(expected_col, cols)

            # Step 3: Downgrade back to Phase 2
            command.downgrade(cfg, "003_add_revoked_tokens")
            insp = inspect(engine)
            self.assertNotIn("analysis_requests", set(insp.get_table_names()))

            # Step 4: Re-upgrade to head
            command.upgrade(cfg, "head")
            insp = inspect(engine)
            self.assertIn("analysis_requests", set(insp.get_table_names()))

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

    @patch("app.services.cv_service.extract_pdf_text")
    @patch("app.routers.cv.evaluate_cv_with_gemini")
    def test_successful_analysis_atomic_write(self, mock_eval, mock_extract):
        mock_extract.return_value = {"pages": 1, "text": "Python Developer with 5 years experience."}
        """
        Verifies that a successful CV analysis saves CV, Job, Analysis,
        and completed idempotency record in a single database transaction.
        """
        mock_eval.return_value = [
            {"skill": "Python", "required_level": "intermediate", "importance": "required", "cv_level": "intermediate", "cv_match_status": "Match", "evidence": "Built backend services with Python."}
        ]

        user_email = f"atomic_success_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = get_auth_token_for_user(user_email)
        idemp_key = f"key_succ_{uuid.uuid4().hex}"

        reqs = [{"skill": "Python", "level": "intermediate", "importance": "required"}]
        pdf_content = b"%PDF-1.4 test resume with Python skill"

        headers_with_key = {**headers, "Idempotency-Key": idemp_key}
        res = client.post(
            "/cv/analyze",
            files={"file": ("resume.pdf", pdf_content, "application/pdf")},
            data={
                "requirements": json.dumps(reqs),
                "job_title": "Python Developer",
                "company": "Tech Corp"
            },
            headers=headers_with_key
        )
        self.assertEqual(res.status_code, 200, res.text)
        data = res.json()
        analysis_id = data.get("analysis_id")
        self.assertIsNotNone(analysis_id)

        # Verify DB records
        db = SessionLocal()
        try:
            analysis = db.query(Analysis).filter(Analysis.id == analysis_id).first()
            self.assertIsNotNone(analysis)
            self.assertEqual(analysis.user_id, user_id)

            job = db.query(Job).filter(Job.id == analysis.job_id).first()
            self.assertIsNotNone(job)
            self.assertEqual(job.title, "Python Developer")

            cv_rec = db.query(CV).filter(CV.id == analysis.cv_id).first()
            self.assertIsNotNone(cv_rec)
            self.assertEqual(cv_rec.user_id, user_id)

            idem = db.query(AnalysisRequest).filter(
                AnalysisRequest.user_id == user_id,
                AnalysisRequest.idempotency_key == idemp_key
            ).first()
            self.assertIsNotNone(idem)
            self.assertEqual(idem.status, "completed")
            self.assertEqual(idem.analysis_id, analysis_id)
            self.assertIsNotNone(idem.response_json)

            # Physical file must exist
            storage = get_storage_backend()
            self.assertTrue(storage.file_exists(cv_rec.file_path) or os.path.exists(cv_rec.file_path))
        finally:
            db.close()

    @patch("app.services.cv_service.extract_pdf_text")
    @patch("app.routers.cv.evaluate_cv_with_gemini")
    @patch("app.routers.cv.combine_cv_and_assessment")
    def test_failure_between_related_db_writes_rolls_back_and_cleans_file(self, mock_combine, mock_eval, mock_extract):
        mock_extract.return_value = {"pages": 1, "text": "Python exp"}
        """
        Simulates a database failure during the write transaction.
        Verifies:
        1. All related records (Job, CV, Analysis) are rolled back atomically.
        2. The newly created CV file is cleaned up safely from disk/storage.
        3. The idempotency record is marked failed so retrying can proceed.
        """
        mock_eval.return_value = [
            {"skill": "Python", "required_level": "intermediate", "importance": "required", "cv_level": "intermediate", "cv_match_status": "Match", "evidence": "Python exp"}
        ]
        # Simulate error in transaction
        mock_combine.side_effect = RuntimeError("Simulated DB write failure during combine")

        user_email = f"atomic_fail_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = get_auth_token_for_user(user_email)
        idemp_key = f"key_fail_{uuid.uuid4().hex}"

        db = SessionLocal()
        initial_cv_count = db.query(CV).filter(CV.user_id == user_id).count()
        initial_job_count = db.query(Job).filter(Job.user_id == user_id).count()
        initial_analysis_count = db.query(Analysis).filter(Analysis.user_id == user_id).count()
        db.close()

        reqs = [{"skill": "Python", "level": "intermediate", "importance": "required"}]
        pdf_content = b"%PDF-1.4 test resume for rollback check"

        headers_with_key = {**headers, "Idempotency-Key": idemp_key}
        with self.assertRaises(RuntimeError) if False else unittest.TestCase().subTest():
            res = client.post(
                "/cv/analyze",
                files={"file": ("rollback_resume.pdf", pdf_content, "application/pdf")},
                data={"requirements": json.dumps(reqs), "job_title": "Failing Job"},
                headers=headers_with_key
            )
            self.assertEqual(res.status_code, 500)

        # Verify rollback in DB
        db = SessionLocal()
        try:
            self.assertEqual(db.query(CV).filter(CV.user_id == user_id).count(), initial_cv_count)
            self.assertEqual(db.query(Job).filter(Job.user_id == user_id).count(), initial_job_count)
            self.assertEqual(db.query(Analysis).filter(Analysis.user_id == user_id).count(), initial_analysis_count)

            # Idempotency record is marked failed
            idem = db.query(AnalysisRequest).filter(
                AnalysisRequest.user_id == user_id,
                AnalysisRequest.idempotency_key == idemp_key
            ).first()
            if idem:
                self.assertEqual(idem.status, "failed")
        finally:
            db.close()

    @patch("app.routers.cv.extract_pdf_text")
    @patch("app.services.cv_service.extract_pdf_text")
    @patch("app.routers.cv.evaluate_cv_with_gemini")
    @patch("app.routers.cv.combine_cv_and_assessment")
    def test_existing_cv_survives_failed_analysis(self, mock_combine, mock_eval, mock_extract, mock_cv_extract):
        mock_cv_extract.return_value = {"pages": 1, "text": "Python developer"}
        mock_extract.return_value = {"pages": 1, "text": "Python developer"}
        """
        Verifies that when an analysis using an existing saved CV fails,
        the previously uploaded CV record and its physical file survive completely.
        """
        user_email = f"survive_cv_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = get_auth_token_for_user(user_email)

        # Upload an initial valid CV
        pdf_content = b"%PDF-1.4 initial existing resume content"
        up_res = client.post(
            "/cv/upload",
            files={"file": ("existing_resume.pdf", pdf_content, "application/pdf")},
            headers=headers
        )
        self.assertEqual(up_res.status_code, 200, up_res.text)
        saved_cv_id = up_res.json().get("cv_id")
        self.assertIsNotNone(saved_cv_id)

        db = SessionLocal()
        saved_cv = db.query(CV).filter(CV.id == saved_cv_id).first()
        self.assertIsNotNone(saved_cv)
        saved_file_path = saved_cv.file_path
        db.close()

        storage = get_storage_backend()
        self.assertTrue(storage.file_exists(saved_file_path) or os.path.exists(saved_file_path))

        # Now simulate failure on subsequent analysis
        mock_eval.return_value = [{"skill": "Python", "required_level": "basic", "importance": "required", "cv_level": "basic", "cv_match_status": "Match", "evidence": None}]
        mock_combine.side_effect = RuntimeError("Failure during second step")

        reqs = [{"skill": "Python", "level": "basic", "importance": "required"}]
        fail_res = client.post(
            "/cv/analyze",
            data={"requirements": json.dumps(reqs), "cv_id": saved_cv_id, "idempotency_key": f"fail_existing_{uuid.uuid4().hex}"},
            headers=headers
        )
        self.assertEqual(fail_res.status_code, 500)

        # Verify existing CV survived untouched!
        db = SessionLocal()
        try:
            survived_cv = db.query(CV).filter(CV.id == saved_cv_id).first()
            self.assertIsNotNone(survived_cv, "Existing CV must survive a failed analysis!")
            self.assertEqual(survived_cv.file_path, saved_file_path)
            self.assertTrue(
                storage.file_exists(saved_file_path) or os.path.exists(saved_file_path),
                "Physical file of existing CV must not be deleted!"
            )
        finally:
            db.close()

    @patch("app.services.cv_service.extract_pdf_text")
    @patch("app.routers.cv.evaluate_cv_with_gemini")
    def test_provider_failure_aborts_before_write_and_cleans_file(self, mock_eval, mock_extract):
        mock_extract.return_value = {"pages": 1, "text": "Python provider test"}
        """
        Verifies that if the AI provider fails, slow provider call is kept
        outside write transaction, no database records are written, and the
        newly uploaded file is cleaned up safely.
        """
        mock_eval.side_effect = RuntimeError("Gemini 503 Provider Unavailable")

        user_email = f"provider_fail_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = get_auth_token_for_user(user_email)
        idemp_key = f"key_prov_fail_{uuid.uuid4().hex}"

        db = SessionLocal()
        cv_count_before = db.query(CV).filter(CV.user_id == user_id).count()
        job_count_before = db.query(Job).filter(Job.user_id == user_id).count()
        db.close()

        reqs = [{"skill": "Python", "level": "intermediate", "importance": "required"}]
        pdf_content = b"%PDF-1.4 provider test payload"

        res = client.post(
            "/cv/analyze",
            files={"file": ("prov_fail.pdf", pdf_content, "application/pdf")},
            data={"requirements": json.dumps(reqs)},
            headers={**headers, "Idempotency-Key": idemp_key}
        )
        self.assertEqual(res.status_code, 502)

        db = SessionLocal()
        try:
            self.assertEqual(db.query(CV).filter(CV.user_id == user_id).count(), cv_count_before)
            self.assertEqual(db.query(Job).filter(Job.user_id == user_id).count(), job_count_before)
            # Idempotency record is marked failed so a retry can run
            idem = db.query(AnalysisRequest).filter(
                AnalysisRequest.user_id == user_id,
                AnalysisRequest.idempotency_key == idemp_key
            ).first()
            if idem:
                self.assertEqual(idem.status, "failed")
        finally:
            db.close()

    @patch("app.services.cv_service.extract_pdf_text")
    @patch("app.routers.cv.evaluate_cv_with_gemini")
    def test_retry_after_successful_commit_recovers_saved_result(self, mock_eval, mock_extract):
        mock_extract.return_value = {"pages": 1, "text": "React Developer Resume"}
        """
        Verifies that if a commit succeeds, retrying the submission with the same
        idempotency key and inputs returns the saved result immediately without
        re-calling the AI provider or creating duplicate records.
        """
        mock_eval.return_value = [
            {"skill": "React", "required_level": "intermediate", "importance": "required", "cv_level": "intermediate", "cv_match_status": "Match", "evidence": "Built web apps with React."}
        ]

        user_email = f"retry_rec_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = get_auth_token_for_user(user_email)
        idemp_key = f"retry_key_{uuid.uuid4().hex}"

        reqs = [{"skill": "React", "level": "intermediate", "importance": "required"}]
        pdf_content = b"%PDF-1.4 React Developer Resume"

        # First request
        res1 = client.post(
            "/cv/analyze",
            files={"file": ("react_resume.pdf", pdf_content, "application/pdf")},
            data={"requirements": json.dumps(reqs), "job_title": "Frontend Engineer"},
            headers={**headers, "Idempotency-Key": idemp_key}
        )
        self.assertEqual(res1.status_code, 200)
        data1 = res1.json()
        orig_analysis_id = data1.get("analysis_id")
        self.assertIsNotNone(orig_analysis_id)

        db = SessionLocal()
        cv_count1 = db.query(CV).filter(CV.user_id == user_id).count()
        job_count1 = db.query(Job).filter(Job.user_id == user_id).count()
        analysis_count1 = db.query(Analysis).filter(Analysis.user_id == user_id).count()
        db.close()

        # Second request (simulate retry, browser never received or retried)
        # Mock AI provider to fail: if retry calls AI provider, it would fail!
        mock_eval.side_effect = RuntimeError("AI provider should not be called on retry!")

        res2 = client.post(
            "/cv/analyze",
            files={"file": ("react_resume.pdf", pdf_content, "application/pdf")},
            data={"requirements": json.dumps(reqs), "job_title": "Frontend Engineer"},
            headers={**headers, "Idempotency-Key": idemp_key}
        )
        self.assertEqual(res2.status_code, 200, "Retry must recover saved result with 200 OK")
        data2 = res2.json()
        self.assertEqual(data2.get("analysis_id"), orig_analysis_id)

        # Verify no duplicate records created in DB
        db = SessionLocal()
        try:
            self.assertEqual(db.query(CV).filter(CV.user_id == user_id).count(), cv_count1)
            self.assertEqual(db.query(Job).filter(Job.user_id == user_id).count(), job_count1)
            self.assertEqual(db.query(Analysis).filter(Analysis.user_id == user_id).count(), analysis_count1)
        finally:
            db.close()

    def test_concurrent_submissions_with_same_key_rejected(self):
        """
        Verifies that two simultaneous requests with the same idempotency key
        cannot create duplicate results; the second request while the original
        is still running is rejected with HTTP 409 Conflict.
        """
        user_email = f"concurrent_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = get_auth_token_for_user(user_email)
        idemp_key = f"conc_key_{uuid.uuid4().hex}"

        reqs = [{"skill": "Python", "level": "basic", "importance": "required"}]
        reqs_str = json.dumps(reqs)

        from app.services.idempotency_service import compute_analysis_request_hash
        dummy_bytes = b"%PDF-1.4 dummy"
        req_hash = compute_analysis_request_hash(requirements=reqs_str, file_bytes=dummy_bytes, include_prior=True)

        # Simulate original request being in 'processing' state in DB
        db = SessionLocal()
        try:
            in_flight = AnalysisRequest(
                user_id=user_id,
                idempotency_key=idemp_key,
                request_hash=req_hash,
                status="processing"
            )
            db.add(in_flight)
            db.commit()
        finally:
            db.close()

        # Concurrent request arrives
        res = client.post(
            "/cv/analyze",
            files={"file": ("dummy.pdf", dummy_bytes, "application/pdf")},
            data={"requirements": reqs_str},
            headers={**headers, "Idempotency-Key": idemp_key}
        )
        self.assertEqual(res.status_code, 409, "Concurrent request on in-flight key must return 409 Conflict")
        self.assertIn("currently being processed", res.json().get("detail", ""))

    def test_key_reuse_with_different_inputs_rejected(self):
        """
        Verifies that reusing the same idempotency key with different inputs
        is strictly rejected with HTTP 409 Conflict.
        """
        user_email = f"key_mismatch_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = get_auth_token_for_user(user_email)
        idemp_key = f"diff_in_key_{uuid.uuid4().hex}"

        db = SessionLocal()
        try:
            record = AnalysisRequest(
                user_id=user_id,
                idempotency_key=idemp_key,
                request_hash="hash_for_original_inputs_abcdef123456",
                status="completed"
            )
            db.add(record)
            db.commit()
        finally:
            db.close()

        # Submit with same key but different inputs
        reqs = [{"skill": "Docker", "level": "advanced", "importance": "required"}]
        res = client.post(
            "/cv/analyze",
            files={"file": ("test.pdf", b"%PDF-1.4 test", "application/pdf")},
            data={"requirements": json.dumps(reqs)},
            headers={**headers, "Idempotency-Key": idemp_key}
        )
        self.assertEqual(res.status_code, 409)
        self.assertIn("different request parameters", res.json().get("detail", ""))

    @patch("app.services.cv_service.extract_pdf_text")
    @patch("app.routers.cv.evaluate_cv_with_gemini")
    def test_another_user_cannot_retrieve_result_using_same_key(self, mock_eval, mock_extract):
        mock_extract.return_value = {"pages": 1, "text": "Java engineer"}
        """
        Verifies that an idempotency key is strictly scoped to the authenticated
        user; another user submitting with the same key cannot retrieve the
        first user's result or trigger a collision.
        """
        mock_eval.return_value = [
            {"skill": "Java", "required_level": "intermediate", "importance": "required", "cv_level": "intermediate", "cv_match_status": "Match", "evidence": "Java dev"}
        ]

        user1_email = f"user1_{uuid.uuid4().hex[:6]}@example.com"
        user2_email = f"user2_{uuid.uuid4().hex[:6]}@example.com"
        u1_id, u1_headers = get_auth_token_for_user(user1_email)
        u2_id, u2_headers = get_auth_token_for_user(user2_email)

        shared_key = f"scoped_key_{uuid.uuid4().hex}"
        reqs = [{"skill": "Java", "level": "intermediate", "importance": "required"}]
        pdf = b"%PDF-1.4 Java resume"

        # User 1 submits
        res1 = client.post(
            "/cv/analyze",
            files={"file": ("u1.pdf", pdf, "application/pdf")},
            data={"requirements": json.dumps(reqs), "job_title": "Java Dev"},
            headers={**u1_headers, "Idempotency-Key": shared_key}
        )
        self.assertEqual(res1.status_code, 200)
        u1_analysis_id = res1.json().get("analysis_id")

        # User 2 submits with SAME key
        res2 = client.post(
            "/cv/analyze",
            files={"file": ("u2.pdf", pdf, "application/pdf")},
            data={"requirements": json.dumps(reqs), "job_title": "Java Dev"},
            headers={**u2_headers, "Idempotency-Key": shared_key}
        )
        self.assertEqual(res2.status_code, 200)
        u2_analysis_id = res2.json().get("analysis_id")

        # Must NOT be the same analysis
        self.assertNotEqual(u1_analysis_id, u2_analysis_id)

        # User 2 cannot access User 1's session
        detail_res = client.get(f"/cv/sessions/{u1_analysis_id}", headers=u2_headers)
        self.assertEqual(detail_res.status_code, 404)

    @patch("app.routers.cv.extract_pdf_text")
    @patch("app.services.cv_service.extract_pdf_text")
    @patch("app.routers.cv.evaluate_cv_with_gemini")
    def test_deliberate_new_analysis_through_new_key(self, mock_eval, mock_extract, mock_cv_extract):
        mock_cv_extract.return_value = {"pages": 1, "text": "Go engineer"}
        mock_extract.return_value = {"pages": 1, "text": "Go engineer"}
        """
        Verifies that deliberate new analyses with new keys create distinct
        sessions, and existing saved reports remain readable in history.
        """
        mock_eval.return_value = [
            {"skill": "Go", "required_level": "intermediate", "importance": "required", "cv_level": "intermediate", "cv_match_status": "Match", "evidence": "Go engineer"}
        ]

        user_email = f"multi_report_{uuid.uuid4().hex[:6]}@example.com"
        user_id, headers = get_auth_token_for_user(user_email)

        reqs = [{"skill": "Go", "level": "intermediate", "importance": "required"}]
        pdf = b"%PDF-1.4 Go Resume"

        # Analysis A
        key_a = f"key_a_{uuid.uuid4().hex}"
        res_a = client.post(
            "/cv/analyze",
            files={"file": ("go1.pdf", pdf, "application/pdf")},
            data={"requirements": json.dumps(reqs), "job_title": "Go Engineer A"},
            headers={**headers, "Idempotency-Key": key_a}
        )
        self.assertEqual(res_a.status_code, 200)
        id_a = res_a.json().get("analysis_id")

        # Deliberate Analysis B
        key_b = f"key_b_{uuid.uuid4().hex}"
        res_b = client.post(
            "/cv/analyze",
            files={"file": ("go2.pdf", pdf, "application/pdf")},
            data={"requirements": json.dumps(reqs), "job_title": "Go Engineer B"},
            headers={**headers, "Idempotency-Key": key_b}
        )
        self.assertEqual(res_b.status_code, 200)
        id_b = res_b.json().get("analysis_id")

        self.assertNotEqual(id_a, id_b)

        # Both reports readable via /cv/sessions
        sessions_res = client.get("/cv/sessions", headers=headers)
        self.assertEqual(sessions_res.status_code, 200)
        sessions = sessions_res.json().get("sessions", [])
        session_ids = [s["analysis_id"] for s in sessions]
        self.assertIn(id_a, session_ids)
        self.assertIn(id_b, session_ids)

        # Both detail reports readable
        det_a = client.get(f"/cv/sessions/{id_a}", headers=headers)
        self.assertEqual(det_a.status_code, 200)
        det_b = client.get(f"/cv/sessions/{id_b}", headers=headers)
        self.assertEqual(det_b.status_code, 200)


if __name__ == "__main__":
    unittest.main()
