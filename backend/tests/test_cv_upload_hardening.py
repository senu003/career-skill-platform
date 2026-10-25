import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


class TestCVUploadHardening(unittest.TestCase):

    def setUp(self):
        import uuid
        uid = str(uuid.uuid4())[:8]
        # Register and login candidate
        reg_res = client.post("/users", json={"name": "Upload User", "email": f"upload_user_{uid}@example.com", "password": "password123"})
        self.user_id = reg_res.json()["id"]
        login_res = client.post("/login", data={"username": f"upload_user_{uid}@example.com", "password": "password123"})
        self.token = login_res.json()["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}

    @patch("app.services.cv_service.extract_pdf_text")
    def test_valid_pdf_upload_accepted(self, mock_extract):
        mock_extract.return_value = {"pages": 1, "text": "Valid CV resume content with Python and React."}
        valid_pdf = b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"
        response = client.post(
            "/cv/upload",
            files={"file": ("resume.pdf", valid_pdf, "application/pdf")},
            headers=self.headers
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["filename"], "resume.pdf")
        self.assertIn("file_path", data)
        self.assertIn("storage_key", data)

    def test_oversized_file_rejected(self):
        # Default limit is 10 MB = 10,485,760 bytes.
        # Create a payload of 10.5 MB starting with PDF header
        oversized_data = b"%PDF-1.4 " + (b"0" * (10 * 1024 * 1024 + 500 * 1024))
        response = client.post(
            "/cv/upload",
            files={"file": ("huge_cv.pdf", oversized_data, "application/pdf")},
            headers=self.headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("File size exceeds maximum allowed limit", response.json()["detail"])

    @patch("app.services.cv_service.extract_pdf_text")
    def test_boundary_condition_exact_limit(self, mock_extract):
        mock_extract.return_value = {"pages": 1, "text": "Boundary test content"}
        # Configure a small custom limit for fast boundary testing: 100 KB
        with patch.dict(os.environ, {"MAX_CV_UPLOAD_SIZE_BYTES": "102400"}):
            # Exactly 102,400 bytes
            exact_data = b"%PDF-1.4 " + (b"A" * (102400 - len(b"%PDF-1.4 ")))
            self.assertEqual(len(exact_data), 102400)

            resp_exact = client.post(
                "/cv/upload",
                files={"file": ("boundary_exact.pdf", exact_data, "application/pdf")},
                headers=self.headers
            )
            self.assertEqual(resp_exact.status_code, 200)

            # 102,401 bytes (1 byte over)
            over_data = exact_data + b"X"
            resp_over = client.post(
                "/cv/upload",
                files={"file": ("boundary_over.pdf", over_data, "application/pdf")},
                headers=self.headers
            )
            self.assertEqual(resp_over.status_code, 400)
            self.assertIn("File size exceeds maximum allowed limit", resp_over.json()["detail"])

    def test_empty_file_rejected(self):
        response = client.post(
            "/cv/upload",
            files={"file": ("empty.pdf", b"", "application/pdf")},
            headers=self.headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Uploaded file is empty", response.json()["detail"])

    def test_non_pdf_extension_rejected(self):
        response = client.post(
            "/cv/upload",
            files={"file": ("resume.docx", b"%PDF-1.4 dummy", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            headers=self.headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Only PDF files are allowed", response.json()["detail"])

    def test_invalid_magic_bytes_rejected(self):
        # Has .pdf extension and application/pdf MIME type, but random non-PDF binary bytes
        corrupted_data = b"\x00\x01\x02\x03\x04\x05FakePDFContentHere"
        response = client.post(
            "/cv/upload",
            files={"file": ("corrupt.pdf", corrupted_data, "application/pdf")},
            headers=self.headers
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("Missing %PDF signature header", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
