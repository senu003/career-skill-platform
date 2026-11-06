import os
import io
import json
import uuid
import unittest
from unittest.mock import patch, MagicMock

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.database import SessionLocal
from app.models import User, CV, Job, Analysis
from app.auth_deps import create_access_token
from app.services.storage_service import (
    StorageBackend,
    LocalStorageBackend,
    S3StorageBackend,
    get_storage_backend,
    reset_storage_backend_for_testing,
    is_s3_path,
)
from scripts.migrate_cvs_to_s3 import migrate_cvs

client = TestClient(app)

SAMPLE_PDF_CONTENT = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\ntrailer\n<< /Root 1 0 R >>\n%%EOF"


class MockS3Client:
    """High-fidelity test double simulating private AWS S3 client operations."""

    def __init__(self):
        self.objects = {}  # (bucket, key) -> dict(body, content_type, sse, acl)
        self.presigned_urls_generated = []

    def put_object(self, Bucket, Key, Body, ContentType="application/pdf", ServerSideEncryption=None, ACL=None):
        self.objects[(Bucket, Key)] = {
            "body": Body if isinstance(Body, bytes) else Body.read(),
            "content_type": ContentType,
            "sse": ServerSideEncryption,
            "acl": ACL,
        }
        return {"ETag": '"mock-etag-123"'}

    def get_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            from botocore.exceptions import ClientError
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}},
                "GetObject"
            )
        data = self.objects[(Bucket, Key)]["body"]
        return {"Body": io.BytesIO(data), "ContentType": self.objects[(Bucket, Key)]["content_type"]}

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            from botocore.exceptions import ClientError
            raise ClientError(
                {"Error": {"Code": "404", "Message": "Not Found"}},
                "HeadObject"
            )
        return {"ContentLength": len(self.objects[(Bucket, Key)]["body"])}

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)
        return {"DeleteMarker": True}

    def generate_presigned_url(self, ClientMethod, Params, ExpiresIn=300):
        url = f"https://mock-s3.amazonaws.com/{Params['Bucket']}/{Params['Key']}?sig=mocked&expires={ExpiresIn}"
        self.presigned_urls_generated.append({"method": ClientMethod, "params": Params, "expires_in": ExpiresIn, "url": url})
        return url


class TestPhase3BPrivateStorage(unittest.TestCase):
    """
    Test suite for Phase 3B: Private CV storage, backend ownership enforcement,
    short-lived signed URLs, failed upload cleanup, and saved report recovery.
    """

    def setUp(self):
        from app.rate_limiter import limiter
        self._limiter_was_enabled = getattr(limiter, "enabled", True)
        limiter.enabled = False

        self.db: Session = SessionLocal()

        # Create two distinct test candidates
        self.user_a_email = f"candidate_a_{uuid.uuid4().hex[:8]}@example.com"
        self.user_b_email = f"candidate_b_{uuid.uuid4().hex[:8]}@example.com"

        user_a = User(name="Candidate A", email=self.user_a_email, password_hash="dummy_hash", is_active=True)
        user_b = User(name="Candidate B", email=self.user_b_email, password_hash="dummy_hash", is_active=True)
        self.db.add_all([user_a, user_b])
        self.db.commit()
        self.db.refresh(user_a)
        self.db.refresh(user_b)

        self.user_a_id = user_a.id
        self.user_b_id = user_b.id

        self.token_a = create_access_token({"sub": str(self.user_a_id)})
        self.token_b = create_access_token({"sub": str(self.user_b_id)})

        self.headers_a = {"Authorization": f"Bearer {self.token_a}"}
        self.headers_b = {"Authorization": f"Bearer {self.token_b}"}

        # Initialize S3 test double
        self.mock_s3 = MockS3Client()
        self.s3_backend = S3StorageBackend(
            bucket_name="private-cv-test-bucket",
            region_name="us-east-1"
        )
        self.s3_backend._client = self.mock_s3
        reset_storage_backend_for_testing(self.s3_backend)

    def tearDown(self):
        from app.rate_limiter import limiter
        limiter.enabled = getattr(self, "_limiter_was_enabled", True)
        reset_storage_backend_for_testing(None)
        self.db.close()

    # --------------------------------------------------------------------------
    # 1. Storage Backend Unit Tests
    # --------------------------------------------------------------------------
    def test_s3_storage_backend_operations(self):
        """Verifies S3StorageBackend save, read, head, presigned URL, and delete."""
        content = b"%PDF-1.4 sample content"
        key, access_path = self.s3_backend.save_file(content, "my_resume.pdf", user_id=self.user_a_id)

        self.assertTrue(access_path.startswith("s3://private-cv-test-bucket/cvs/"))
        self.assertTrue(self.s3_backend.file_exists(access_path))
        self.assertTrue(self.s3_backend.file_exists(key))

        # Verify encryption and private ACL
        raw_obj = self.mock_s3.objects[("private-cv-test-bucket", key)]
        self.assertEqual(raw_obj["sse"], "AES256")
        self.assertEqual(raw_obj["acl"], "private")

        # Verify get_file_bytes
        retrieved = self.s3_backend.get_file_bytes(access_path)
        self.assertEqual(retrieved, content)

        # Verify presigned URL generation
        signed_url = self.s3_backend.generate_presigned_url(access_path, expires_in=300, filename="my_resume.pdf")
        self.assertIsNotNone(signed_url)
        self.assertIn("private-cv-test-bucket", signed_url)
        self.assertIn("expires=300", signed_url)

        # Verify deletion
        deleted = self.s3_backend.delete_file(access_path)
        self.assertTrue(deleted)
        self.assertFalse(self.s3_backend.file_exists(access_path))

    def test_local_storage_backend_operations_and_traversal_defense(self):
        """Verifies LocalStorageBackend safe directory traversal prevention."""
        local = LocalStorageBackend()
        content = b"%PDF-1.4 local sample"
        key, path = local.save_file(content, "local_test.pdf", user_id=self.user_a_id)

        try:
            self.assertTrue(local.file_exists(path))
            self.assertEqual(local.get_file_bytes(path), content)
            self.assertIsNone(local.generate_presigned_url(path))

            # Directory traversal attempt
            traversal_key = "../../../etc/passwd"
            safe_resolved = local._resolve_safe_path(traversal_key)
            self.assertTrue(safe_resolved.startswith(local.base_dir))
        finally:
            local.delete_file(path)

    # --------------------------------------------------------------------------
    # 2. Owner Access vs Cross-User Denial (IDOR) on Download & Signed URL
    # --------------------------------------------------------------------------
    @patch("app.services.cv_service.extract_pdf_text")
    def test_cv_download_owner_access_and_cross_user_denial(self, mock_pdf):
        """Owner can download CV; unauthorized candidate receives 403 Forbidden."""
        mock_pdf.return_value = {"pages": 1, "text": "Candidate A Resume Text"}

        # Upload CV for User A
        upload_res = client.post(
            "/cv/upload",
            files={"file": ("candidate_a.pdf", SAMPLE_PDF_CONTENT, "application/pdf")},
            headers=self.headers_a
        )
        self.assertEqual(upload_res.status_code, 200)
        cv_id = upload_res.json()["cv_id"]
        self.assertTrue(upload_res.json()["file_path"].startswith("s3://"))

        # User A (Owner) downloads CV -> 200 OK
        dl_res = client.get(f"/cv/{cv_id}/download", headers=self.headers_a)
        self.assertEqual(dl_res.status_code, 200)
        self.assertEqual(dl_res.headers["content-type"], "application/pdf")
        self.assertEqual(dl_res.content, SAMPLE_PDF_CONTENT)

        # User B (Cross-User) attempts download -> 403 Forbidden
        dl_res_b = client.get(f"/cv/{cv_id}/download", headers=self.headers_b)
        self.assertEqual(dl_res_b.status_code, 403)
        self.assertIn("Not authorized", dl_res_b.json()["detail"])

        # Non-existent CV -> 404 Not Found
        dl_res_404 = client.get("/cv/99999999/download", headers=self.headers_a)
        self.assertEqual(dl_res_404.status_code, 404)

    @patch("app.services.cv_service.extract_pdf_text")
    def test_cv_signed_url_owner_access_and_cross_user_denial(self, mock_pdf):
        """Owner obtains short-lived signed URL; unauthorized candidate receives 403 Forbidden."""
        mock_pdf.return_value = {"pages": 1, "text": "Candidate A Resume"}

        # Upload CV for User A
        upload_res = client.post(
            "/cv/upload",
            files={"file": ("candidate_a.pdf", SAMPLE_PDF_CONTENT, "application/pdf")},
            headers=self.headers_a
        )
        cv_id = upload_res.json()["cv_id"]

        # User A requests signed URL -> 200 with presigned URL
        url_res = client.get(f"/cv/{cv_id}/signed-url?expires_in=600", headers=self.headers_a)
        self.assertEqual(url_res.status_code, 200)
        data = url_res.json()
        self.assertTrue(data["is_presigned"])
        self.assertIn("https://mock-s3.amazonaws.com/", data["download_url"])
        self.assertEqual(data["expires_in"], 600)
        # Ensure AWS credentials are NOT in the response
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", json.dumps(data))

        # User B requests signed URL for User A's CV -> 403 Forbidden
        url_res_b = client.get(f"/cv/{cv_id}/signed-url", headers=self.headers_b)
        self.assertEqual(url_res_b.status_code, 403)
        self.assertIn("Not authorized", url_res_b.json()["detail"])

    # --------------------------------------------------------------------------
    # 3. Failed Upload and Analysis Cleanup (Phase 3A Rollback Preservation)
    # --------------------------------------------------------------------------
    @patch("sqlalchemy.orm.Session.commit")
    @patch("app.services.cv_service.extract_pdf_text")
    def test_failed_upload_cleans_up_s3_file(self, mock_pdf, mock_commit):
        """If database commit fails during upload, newly stored S3 object is safely deleted."""
        mock_pdf.return_value = {"pages": 1, "text": "Candidate A"}
        mock_commit.side_effect = Exception("Simulated DB Commit Failure")

        upload_res = client.post(
            "/cv/upload",
            files={"file": ("fail_upload.pdf", SAMPLE_PDF_CONTENT, "application/pdf")},
            headers=self.headers_a
        )
        self.assertEqual(upload_res.status_code, 500)
        # Verify no orphan objects remaining in S3 mock
        self.assertEqual(len(self.mock_s3.objects), 0)

    @patch("app.routers.cv.evaluate_cv_with_gemini")
    @patch("app.services.cv_service.extract_pdf_text")
    def test_analysis_provider_failure_cleans_only_new_s3_file(self, mock_pdf, mock_eval):
        """If AI provider fails during analysis, only the new S3 file is deleted; existing CV survives."""
        mock_pdf.return_value = {"pages": 1, "text": "Candidate A"}
        mock_eval.side_effect = Exception("Simulated Provider Down (502)")

        # 1. Existing CV previously stored in S3
        existing_key, existing_path = self.s3_backend.save_file(SAMPLE_PDF_CONTENT, "existing.pdf", user_id=self.user_a_id)
        existing_cv = CV(user_id=self.user_a_id, file_name="existing.pdf", file_path=existing_path)
        self.db.add(existing_cv)
        self.db.commit()
        self.db.refresh(existing_cv)

        self.assertTrue(self.s3_backend.file_exists(existing_path))

        # 2. Attempt analysis with a NEW uploaded file that triggers provider failure
        res = client.post(
            "/cv/analyze",
            data={
                "requirements": json.dumps([{"skill": "Python", "level": "basic", "importance": "required"}]),
                "idempotency_key": "prov_fail_s3_key"
            },
            files={"file": ("new_attempt.pdf", SAMPLE_PDF_CONTENT, "application/pdf")},
            headers=self.headers_a
        )
        self.assertEqual(res.status_code, 502)

        # 3. The new S3 file must be cleaned up, but existing CV must survive intact
        self.assertTrue(self.s3_backend.file_exists(existing_path))
        surviving_cv = self.db.query(CV).filter(CV.id == existing_cv.id).first()
        self.assertIsNotNone(surviving_cv)

    # --------------------------------------------------------------------------
    # 4. Reopening Saved Report from History with S3 Storage
    # --------------------------------------------------------------------------
    @patch("app.services.cv_service.extract_pdf_text")
    def test_reopen_saved_report_with_s3_storage(self, mock_pdf):
        """Historical analysis whose CV is stored in S3 can be reopened from History smoothly."""
        mock_pdf.return_value = {"pages": 1, "text": "Python Developer with AWS experience"}

        # Save CV in S3
        key, s3_path = self.s3_backend.save_file(SAMPLE_PDF_CONTENT, "resume_s3.pdf", user_id=self.user_a_id)
        cv_rec = CV(user_id=self.user_a_id, file_name="resume_s3.pdf", file_path=s3_path)
        self.db.add(cv_rec)
        self.db.flush()

        # Create Job & Analysis session
        job_rec = Job(
            user_id=self.user_a_id,
            title="Backend Cloud Engineer",
            company="Tech Corp",
            description=json.dumps([{"skill": "Python", "level": "intermediate", "importance": "required"}])
        )
        self.db.add(job_rec)
        self.db.flush()

        eval_skills = [{
            "skill": "Python",
            "required_level": "intermediate",
            "importance": "required",
            "cv_level": "intermediate",
            "cv_match_status": "Match",
            "evidence": "Python developer",
            "actionable_feedback": None
        }]
        analysis_rec = Analysis(
            user_id=self.user_a_id,
            job_id=job_rec.id,
            cv_id=cv_rec.id,
            overall_score=85,
            raw_analysis_data=json.dumps(eval_skills)
        )
        self.db.add(analysis_rec)
        self.db.commit()
        self.db.refresh(analysis_rec)

        # Fetch session list from /cv/sessions
        sessions_res = client.get("/cv/sessions", headers=self.headers_a)
        self.assertEqual(sessions_res.status_code, 200)
        sessions_list = sessions_res.json()["sessions"]
        self.assertTrue(len(sessions_list) >= 1)
        self.assertEqual(sessions_list[0]["job_title"], "Backend Cloud Engineer")

        # Fetch session detail from /cv/sessions/{id}
        detail_res = client.get(f"/cv/sessions/{analysis_rec.id}", headers=self.headers_a)
        self.assertEqual(detail_res.status_code, 200)
        detail_data = detail_res.json()
        self.assertEqual(detail_data["job_title"], "Backend Cloud Engineer")
        self.assertEqual(detail_data["score_data"]["score"], 100.0)

    # --------------------------------------------------------------------------
    # 5. Backward Compatibility & Standalone S3 Migration Utility
    # --------------------------------------------------------------------------
    def test_backward_compatibility_with_legacy_local_cv_files(self):
        """Historical local CV files continue to be downloadable when S3 backend is active."""
        local = LocalStorageBackend()
        _, local_path = local.save_file(SAMPLE_PDF_CONTENT, "legacy_local.pdf", user_id=self.user_a_id)

        try:
            cv_legacy = CV(user_id=self.user_a_id, file_name="legacy_local.pdf", file_path=local_path)
            self.db.add(cv_legacy)
            self.db.commit()
            self.db.refresh(cv_legacy)

            # Even though current backend is S3, downloading legacy file succeeds via fallback
            dl_res = client.get(f"/cv/{cv_legacy.id}/download", headers=self.headers_a)
            self.assertEqual(dl_res.status_code, 200)
            self.assertEqual(dl_res.content, SAMPLE_PDF_CONTENT)
        finally:
            local.delete_file(local_path)

    def test_migrate_cvs_to_s3_utility(self):
        """Verifies migrate_cvs script discovers and migrates local files to S3."""
        local = LocalStorageBackend()
        _, local_path = local.save_file(SAMPLE_PDF_CONTENT, "to_migrate.pdf", user_id=self.user_a_id)

        try:
            cv_to_mig = CV(user_id=self.user_a_id, file_name="to_migrate.pdf", file_path=local_path)
            self.db.add(cv_to_mig)
            self.db.commit()
            self.db.refresh(cv_to_mig)

            # 1. Test Dry-Run scoped to test candidate
            found, migrated, errors = migrate_cvs(dry_run=True, remove_local=False, user_id=self.user_a_id)
            self.assertEqual(found, 1)
            self.assertEqual(migrated, 1)
            self.assertEqual(errors, 0)

            # Database should not have changed in dry-run
            self.db.refresh(cv_to_mig)
            self.assertFalse(str(cv_to_mig.file_path).startswith("s3://"))

            # 2. Test Live Migration
            with patch("scripts.migrate_cvs_to_s3.S3StorageBackend", return_value=self.s3_backend):
                found, migrated, errors = migrate_cvs(dry_run=False, remove_local=False, user_id=self.user_a_id)
                self.assertEqual(found, 1)
                self.assertEqual(migrated, 1)
                self.assertEqual(errors, 0)

                self.db.refresh(cv_to_mig)
                self.assertTrue(str(cv_to_mig.file_path).startswith("s3://"))
                self.assertTrue(self.s3_backend.file_exists(cv_to_mig.file_path))
        finally:
            local.delete_file(local_path)


if __name__ == "__main__":
    unittest.main()
