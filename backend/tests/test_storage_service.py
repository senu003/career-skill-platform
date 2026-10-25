import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.storage_service import (
    LocalStorageBackend,
    S3StorageBackend,
    get_storage_backend,
    reset_storage_backend_for_testing,
)


class TestStorageService(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.local_backend = LocalStorageBackend(base_dir=self.temp_dir)

    def tearDown(self):
        import shutil
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir, ignore_errors=True)
        reset_storage_backend_for_testing(None)

    def test_local_storage_save_and_retrieve(self):
        content = b"%PDF-1.4 test resume bytes"
        key, path = self.local_backend.save_file(content, "my_resume.pdf", user_id=123)

        self.assertTrue(key.startswith("cvs/123/"))
        self.assertTrue(key.endswith(".pdf"))
        self.assertTrue(self.local_backend.file_exists(path))

        retrieved = self.local_backend.get_file_bytes(path)
        self.assertEqual(retrieved, content)

    def test_directory_traversal_protection(self):
        # Attempt traversal with ../../../etc/passwd or similar
        malicious_key = "../../../secret.txt"
        resolved = self.local_backend._resolve_safe_path(malicious_key)
        self.assertTrue(resolved.startswith(self.temp_dir))
        self.assertFalse(".." in resolved)

    def test_local_storage_deletion(self):
        content = b"%PDF-1.4 test resume for deletion"
        key, path = self.local_backend.save_file(content, "del.pdf", user_id=456)
        self.assertTrue(self.local_backend.file_exists(path))

        deleted = self.local_backend.delete_file(path)
        self.assertTrue(deleted)
        self.assertFalse(self.local_backend.file_exists(path))

    def test_local_storage_nonexistent_file(self):
        self.assertFalse(self.local_backend.file_exists("nonexistent_uuid.pdf"))
        with self.assertRaises(FileNotFoundError):
            self.local_backend.get_file_bytes("nonexistent_uuid.pdf")

    def test_s3_storage_interface_and_naming(self):
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            s3_backend = S3StorageBackend(bucket_name="test-bucket")
            s3_backend._client = mock_client

            content = b"%PDF-1.4 mock s3 cv"
            key, s3_uri = s3_backend.save_file(content, "candidate.pdf", user_id=789)

            self.assertTrue(key.startswith("cvs/789/"))
            self.assertTrue(key.endswith(".pdf"))
            self.assertEqual(s3_uri, f"s3://test-bucket/{key}")

            # Verify ServerSideEncryption was requested
            mock_client.put_object.assert_called_once()
            call_kwargs = mock_client.put_object.call_args[1]
            self.assertEqual(call_kwargs["Bucket"], "test-bucket")
            self.assertEqual(call_kwargs["Key"], key)
            self.assertEqual(call_kwargs["ServerSideEncryption"], "AES256")

    def test_factory_respects_storage_backend_env(self):
        reset_storage_backend_for_testing(None)
        with patch.dict(os.environ, {"STORAGE_BACKEND": "local"}):
            backend = get_storage_backend()
            self.assertIsInstance(backend, LocalStorageBackend)

        reset_storage_backend_for_testing(None)
        with patch.dict(os.environ, {"STORAGE_BACKEND": "s3"}):
            backend_s3 = get_storage_backend()
            self.assertIsInstance(backend_s3, S3StorageBackend)


if __name__ == "__main__":
    unittest.main()
