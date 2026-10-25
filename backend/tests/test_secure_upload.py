import os
import sys
import unittest
from unittest.mock import patch, AsyncMock
from io import BytesIO

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.datastructures import UploadFile, Headers

from app.services.cv_service import (
    process_cv,
    get_max_upload_size_bytes,
    get_max_upload_size_mb,
)
from app.services.storage_service import StorageService
from app.main import app

client = TestClient(app)


class TestSecurePDFUpload(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Default test header
        self.pdf_headers = Headers({"content-type": "application/pdf"})

    def _create_mock_upload_file(self, filename: str, content: bytes, content_type: str = "application/pdf") -> UploadFile:
        file_obj = BytesIO(content)
        headers = Headers({"content-type": content_type})
        return UploadFile(file=file_obj, size=len(content), filename=filename, headers=headers)

    @patch("app.services.cv_service.extract_pdf_text")
    async def test_valid_pdf_upload_success(self, mock_extract):
        mock_extract.return_value = {"pages": 1, "text": "Valid CV Text", "parsing_method": "pypdf", "parse_quality_score": 1.0}
        
        valid_content = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF"
        upload_file = self._create_mock_upload_file("resume.pdf", valid_content)
        
        result = await process_cv(upload_file)
        self.assertEqual(result["filename"], "resume.pdf")
        self.assertEqual(result["pages"], 1)
        self.assertEqual(result["text"], "Valid CV Text")
        self.assertTrue(os.path.exists(result["file_path"]))
        
        # Clean up
        if os.path.exists(result["file_path"]):
            os.remove(result["file_path"])

    async def test_empty_file_rejected(self):
        upload_file = self._create_mock_upload_file("empty.pdf", b"")
        with self.assertRaises(HTTPException) as ctx:
            await process_cv(upload_file)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Uploaded file is empty", ctx.exception.detail)

    async def test_invalid_extension_rejected(self):
        upload_file = self._create_mock_upload_file("script.sh", b"%PDF-1.4 dummy", content_type="text/x-sh")
        with self.assertRaises(HTTPException) as ctx:
            await process_cv(upload_file)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Only PDF files are allowed", ctx.exception.detail)

    async def test_invalid_magic_bytes_rejected(self):
        # Has .pdf extension and application/pdf MIME, but content is not a real PDF
        fake_content = b"NOT_A_PDF_CONTENT_HERE"
        upload_file = self._create_mock_upload_file("fake.pdf", fake_content)
        with self.assertRaises(HTTPException) as ctx:
            await process_cv(upload_file)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Invalid PDF file", ctx.exception.detail)

    async def test_oversized_file_rejected_default_10mb(self):
        # 10 MB = 10 * 1024 * 1024 bytes = 10,485,760 bytes
        # Create file with 10MB + 100 bytes
        oversized_len = (10 * 1024 * 1024) + 100
        oversized_content = b"%PDF" + (b"A" * (oversized_len - 4))
        
        upload_file = self._create_mock_upload_file("huge.pdf", oversized_content)
        with self.assertRaises(HTTPException) as ctx:
            await process_cv(upload_file)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("File size exceeds maximum allowed limit", ctx.exception.detail)

    @patch("app.services.cv_service.extract_pdf_text")
    async def test_boundary_condition_under_and_over_limit(self, mock_extract):
        mock_extract.return_value = {"pages": 1, "text": "Boundary test"}
        
        # Test with custom limit of 1 MB for testing boundary precision
        with patch.dict(os.environ, {"MAX_UPLOAD_SIZE_MB": "1"}):
            max_limit = 1 * 1024 * 1024
            self.assertEqual(get_max_upload_size_bytes(), max_limit)
            
            # Boundary 1: Exactly at limit -> ACCEPTED
            exact_content = b"%PDF" + (b"0" * (max_limit - 4))
            upload_exact = self._create_mock_upload_file("exact.pdf", exact_content)
            res_exact = await process_cv(upload_exact)
            self.assertEqual(res_exact["filename"], "exact.pdf")
            if os.path.exists(res_exact["file_path"]):
                os.remove(res_exact["file_path"])
                
            # Boundary 2: 1 byte over limit -> REJECTED
            over_content = b"%PDF" + (b"0" * (max_limit - 4 + 1))
            upload_over = self._create_mock_upload_file("over.pdf", over_content)
            with self.assertRaises(HTTPException) as ctx:
                await process_cv(upload_over)
            self.assertEqual(ctx.exception.status_code, 400)
            self.assertIn("File size exceeds maximum allowed limit of 1MB", ctx.exception.detail)

    @patch("app.services.cv_service.extract_pdf_text")
    def test_api_cv_upload_endpoint_oversized_rejection(self, mock_extract):
        # Register and login candidate
        import uuid
        uid = str(uuid.uuid4())[:8]
        client.post("/users", json={"name": "Upload Cand", "email": f"up_{uid}@example.com", "password": "pass"})
        tok = client.post("/login", data={"username": f"up_{uid}@example.com", "password": "pass"}).json()["access_token"]
        headers = {"Authorization": f"Bearer {tok}"}
        
        # Upload oversized content (> 10MB) via HTTP
        oversized_content = b"%PDF" + (b"Z" * (10 * 1024 * 1024 + 1024))
        files = {"file": ("big_resume.pdf", oversized_content, "application/pdf")}
        
        resp = client.post("/cv/upload", files=files, headers=headers)
        self.assertEqual(resp.status_code, 400)
        self.assertIn("File size exceeds maximum allowed limit", resp.json()["detail"])


class TestStorageService(unittest.TestCase):

    def setUp(self):
        import tempfile
        self.temp_dir = tempfile.mkdtemp()
        self.storage = StorageService(base_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_save_get_and_delete_file(self):
        content = b"%PDF-1.4 test document content"
        storage_key, file_path = self.storage.save_file(content, original_filename="test.pdf")
        
        self.assertTrue(self.storage.file_exists(file_path))
        retrieved_bytes = self.storage.get_file_bytes(file_path)
        self.assertEqual(retrieved_bytes, content)
        
        # Local path
        safe_path = self.storage._resolve_safe_path(file_path)
        self.assertTrue(os.path.exists(safe_path))
        
        # Delete file
        deleted = self.storage.delete_file(file_path)
        self.assertTrue(deleted)
        self.assertFalse(self.storage.file_exists(file_path))


if __name__ == "__main__":
    unittest.main()
