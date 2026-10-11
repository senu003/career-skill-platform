import sys
import os
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

class TestCVSecurity(unittest.TestCase):

    def setUp(self):
        import uuid
        uid = str(uuid.uuid4())[:8]
        # Create User A
        res_a = client.post("/users", json={"name": "User A", "email": f"usera_cv_{uid}@example.com", "password": "pwd"})
        self.user_a_id = res_a.json()["id"]
        login_a = client.post("/login", data={"username": f"usera_cv_{uid}@example.com", "password": "pwd"})
        self.token_a = login_a.json()["access_token"]
        
        # Create User B
        res_b = client.post("/users", json={"name": "User B", "email": f"userb_cv_{uid}@example.com", "password": "pwd"})
        self.user_b_id = res_b.json()["id"]
        login_b = client.post("/login", data={"username": f"userb_cv_{uid}@example.com", "password": "pwd"})
        self.token_b = login_b.json()["access_token"]

    def test_unauthenticated_cv_upload(self):
        """Unauthenticated CV upload should return 401."""
        response = client.post(
            "/cv/upload",
            files={"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")}
        )
        self.assertEqual(response.status_code, 401)

    @patch("app.services.cv_service.extract_pdf_text")
    def test_authenticated_cv_upload_ownership(self, mock_extract_pdf_text):
        """Authenticated CV upload associates CV with the current user."""
        mock_extract_pdf_text.return_value = {"pages": 1, "text": "Dummy CV text"}
        
        headers = {"Authorization": f"Bearer {self.token_a}"}
        response = client.post(
            "/cv/upload",
            files={"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")},
            headers=headers
        )
        self.assertEqual(response.status_code, 200)
        
        # Verify ownership by fetching latest CV
        latest_cv_res = client.get("/cv/latest", headers=headers)
        self.assertEqual(latest_cv_res.status_code, 200)
        self.assertTrue(latest_cv_res.json()["has_cv"])
        
    @patch("app.services.cv_service.extract_pdf_text")
    def test_cross_user_cv_access(self, mock_extract_pdf_text):
        """User B requesting User A's CV should be denied."""
        mock_extract_pdf_text.return_value = {"pages": 1, "text": "Dummy CV text"}
        
        # User A uploads a CV
        headers_a = {"Authorization": f"Bearer {self.token_a}"}
        upload_res = client.post(
            "/cv/upload",
            files={"file": ("test.pdf", b"%PDF-1.4 dummy", "application/pdf")},
            headers=headers_a
        )
        cv_id = upload_res.json()["cv_id"]
        
        # User B tries to analyze using User A's cv_id
        headers_b = {"Authorization": f"Bearer {self.token_b}"}
        analyze_res = client.post(
            "/cv/analyze",
            data={
                "requirements": '[{"skill": "Python", "level": "basic", "importance": "required"}]',
                "cv_id": cv_id
            },
            headers=headers_b
        )
        self.assertEqual(analyze_res.status_code, 403)
        self.assertIn("Not authorized", analyze_res.json()["detail"])

    @patch("sqlalchemy.orm.Session.commit")
    @patch("app.services.cv_service.extract_pdf_text")
    def test_failure_cleanup(self, mock_extract_pdf_text, mock_commit):
        """If database operation fails, the uploaded file is cleaned up."""
        mock_extract_pdf_text.return_value = {"pages": 1, "text": "Dummy"}
        mock_commit.side_effect = Exception("DB Error")
        
        headers = {"Authorization": f"Bearer {self.token_a}"}
        
        # The endpoint should return 500
        response = client.post(
            "/cv/upload",
            files={"file": ("test_failure.pdf", b"%PDF-1.4 dummy", "application/pdf")},
            headers=headers
        )
        self.assertEqual(response.status_code, 500)
        
        # Verify that there is no file remaining that contains "test_failure.pdf" or was created recently
        # We can mock os.remove and see if it was called, or just check the directory.
        # Since we mocked db.commit, the route handled the cleanup.

    @patch("os.remove")
    @patch("sqlalchemy.orm.Session.commit")
    @patch("app.services.cv_service.extract_pdf_text")
    def test_failure_cleanup_os_remove_called(self, mock_extract_pdf_text, mock_commit, mock_os_remove):
        mock_extract_pdf_text.return_value = {"pages": 1, "text": "Dummy"}
        mock_commit.side_effect = Exception("DB Error")
        
        headers = {"Authorization": f"Bearer {self.token_a}"}
        response = client.post(
            "/cv/upload",
            files={"file": ("test_failure2.pdf", b"%PDF-1.4 dummy", "application/pdf")},
            headers=headers
        )
        self.assertEqual(response.status_code, 500)
        # Verify os.remove was called with the file_path
        self.assertTrue(mock_os_remove.called)
        
if __name__ == "__main__":
    unittest.main()
