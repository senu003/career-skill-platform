import os
import uuid
import logging
from abc import ABC, abstractmethod
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class StorageBackend(ABC):
    """Abstract interface for CV file storage."""

    @abstractmethod
    def save_file(self, content: bytes, original_filename: str, user_id: Optional[int] = None) -> Tuple[str, str]:
        """
        Saves file bytes securely.
        Returns (storage_key, access_path).
        """
        pass

    @abstractmethod
    def get_file_bytes(self, storage_path_or_key: str) -> bytes:
        """Retrieves raw file bytes."""
        pass

    @abstractmethod
    def delete_file(self, storage_path_or_key: str) -> bool:
        """Deletes file from storage."""
        pass

    @abstractmethod
    def file_exists(self, storage_path_or_key: str) -> bool:
        """Checks if file exists in storage."""
        pass


class LocalStorageBackend(StorageBackend):
    """
    Local filesystem storage with safe path resolution, directory traversal protection,
    and private file permissions.
    """

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = os.path.abspath(base_dir or os.getenv("UPLOAD_DIR", "uploads"))
        os.makedirs(self.base_dir, exist_ok=True)

    def _resolve_safe_path(self, storage_path_or_key: str) -> str:
        """
        Resolves path and guarantees it resides within self.base_dir.
        Defends against directory traversal (../ attacks).
        """
        # If absolute path, verify it's inside base_dir or relative to base_dir
        if os.path.isabs(storage_path_or_key):
            resolved = os.path.abspath(storage_path_or_key)
        else:
            resolved = os.path.abspath(os.path.join(self.base_dir, os.path.basename(storage_path_or_key)))

        # Also support legacy relative paths like "uploads/xyz.pdf"
        if not resolved.startswith(self.base_dir):
            clean_name = os.path.basename(storage_path_or_key)
            resolved = os.path.abspath(os.path.join(self.base_dir, clean_name))

        return resolved

    def save_file(self, content: bytes, original_filename: str, user_id: Optional[int] = None) -> Tuple[str, str]:
        file_id = str(uuid.uuid4())
        safe_name = f"{file_id}.pdf"
        target_path = os.path.join(self.base_dir, safe_name)

        # Write file with restrictive permissions (0o600 where supported)
        with open(target_path, "wb") as f:
            f.write(content)

        try:
            os.chmod(target_path, 0o600)
        except (OSError, AttributeError):
            pass  # Windows or restricted filesystem

        storage_key = f"cvs/{user_id or 'anon'}/{safe_name}"
        # For backward compatibility, access_path is the relative/normalized path
        try:
            access_path = os.path.relpath(target_path).replace("\\", "/")
        except ValueError:
            access_path = target_path.replace("\\", "/")
        return storage_key, access_path

    def get_file_bytes(self, storage_path_or_key: str) -> bytes:
        safe_path = self._resolve_safe_path(storage_path_or_key)
        if not os.path.exists(safe_path):
            raise FileNotFoundError(f"CV file not found: {storage_path_or_key}")
        with open(safe_path, "rb") as f:
            return f.read()

    def delete_file(self, storage_path_or_key: str) -> bool:
        try:
            safe_path = self._resolve_safe_path(storage_path_or_key)
            if os.path.exists(safe_path):
                os.remove(safe_path)
                return True
            return False
        except Exception as e:
            logger.warning(f"Failed to delete file {storage_path_or_key}: {e}")
            return False

    def file_exists(self, storage_path_or_key: str) -> bool:
        safe_path = self._resolve_safe_path(storage_path_or_key)
        return os.path.exists(safe_path)


class S3StorageBackend(StorageBackend):
    """
    Private S3 / S3-compatible (MinIO, Cloud Storage) object storage backend.
    Enforces private object ACLs and strict isolation.
    """

    def __init__(
        self,
        bucket_name: Optional[str] = None,
        endpoint_url: Optional[str] = None,
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
    ):
        self.bucket_name = bucket_name or os.getenv("S3_BUCKET_NAME", "career-skill-cv-uploads")
        self.endpoint_url = endpoint_url or os.getenv("S3_ENDPOINT_URL")
        self.region_name = region_name or os.getenv("AWS_REGION", "us-east-1")
        self.aws_access_key_id = aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_access_key = aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    "s3",
                    endpoint_url=self.endpoint_url,
                    region_name=self.region_name,
                    aws_access_key_id=self.aws_access_key_id,
                    aws_secret_access_key=self.aws_secret_access_key,
                )
            except ImportError:
                raise RuntimeError("boto3 is required for S3StorageBackend. Install boto3 or set STORAGE_BACKEND=local.")
        return self._client

    def save_file(self, content: bytes, original_filename: str, user_id: Optional[int] = None) -> Tuple[str, str]:
        file_id = str(uuid.uuid4())
        safe_key = f"cvs/{user_id or 'anon'}/{file_id}.pdf"
        client = self._get_client()
        client.put_object(
            Bucket=self.bucket_name,
            Key=safe_key,
            Body=content,
            ContentType="application/pdf",
            ServerSideEncryption="AES256",
        )
        # Store safe S3 URI as access_path
        access_path = f"s3://{self.bucket_name}/{safe_key}"
        return safe_key, access_path

    def get_file_bytes(self, storage_path_or_key: str) -> bytes:
        client = self._get_client()
        key = storage_path_or_key.replace(f"s3://{self.bucket_name}/", "").lstrip("/")
        resp = client.get_object(Bucket=self.bucket_name, Key=key)
        return resp["Body"].read()

    def delete_file(self, storage_path_or_key: str) -> bool:
        try:
            client = self._get_client()
            key = storage_path_or_key.replace(f"s3://{self.bucket_name}/", "").lstrip("/")
            client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception as e:
            logger.warning(f"S3 delete failed for {storage_path_or_key}: {e}")
            return False

    def file_exists(self, storage_path_or_key: str) -> bool:
        try:
            client = self._get_client()
            key = storage_path_or_key.replace(f"s3://{self.bucket_name}/", "").lstrip("/")
            client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except Exception:
            return False


_STORAGE_INSTANCE: Optional[StorageBackend] = None


def get_storage_backend() -> StorageBackend:
    """Returns singleton configured storage backend."""
    global _STORAGE_INSTANCE
    if _STORAGE_INSTANCE is None:
        backend_type = os.getenv("STORAGE_BACKEND", "local").lower().strip()
        if backend_type == "s3":
            _STORAGE_INSTANCE = S3StorageBackend()
        else:
            _STORAGE_INSTANCE = LocalStorageBackend()
    return _STORAGE_INSTANCE


def reset_storage_backend_for_testing(backend: Optional[StorageBackend] = None):
    """Allows testing harnesses to swap or reset storage backend."""
    global _STORAGE_INSTANCE
    _STORAGE_INSTANCE = backend


class _StorageServiceProxy:
    def __getattr__(self, name):
        return getattr(get_storage_backend(), name)

    def save_file(self, content: bytes, original_filename: str = "resume.pdf", user_id: Optional[int] = None, extension: str = ".pdf") -> Tuple[str, str]:
        backend = get_storage_backend()
        return backend.save_file(content=content, original_filename=original_filename, user_id=user_id)

    def get_local_path(self, storage_path_or_key: str) -> str:
        backend = get_storage_backend()
        if hasattr(backend, "_resolve_safe_path"):
            return backend._resolve_safe_path(storage_path_or_key)
        return storage_path_or_key


default_storage = _StorageServiceProxy()
StorageService = LocalStorageBackend
