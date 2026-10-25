import os
import logging
from typing import Optional

from fastapi import UploadFile, HTTPException

from .pdf_service import extract_pdf_text
from .storage_service import get_storage_backend

logger = logging.getLogger(__name__)

# Default maximum upload limit: 10 MB (10,485,760 bytes)
DEFAULT_MAX_CV_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024


def get_max_upload_size_bytes() -> int:
    mb_env = os.getenv("MAX_UPLOAD_SIZE_MB")
    if mb_env:
        try:
            return int(float(mb_env) * 1024 * 1024)
        except (ValueError, TypeError):
            pass
    try:
        return int(os.getenv("MAX_CV_UPLOAD_SIZE_BYTES", str(DEFAULT_MAX_CV_UPLOAD_SIZE_BYTES)))
    except (ValueError, TypeError):
        return DEFAULT_MAX_CV_UPLOAD_SIZE_BYTES


def get_max_upload_size_mb() -> float:
    return get_max_upload_size_bytes() / (1024 * 1024)


async def read_bounded_file(file: UploadFile, max_bytes: int) -> bytes:
    """
    Safely reads uploaded file stream up to max_bytes without buffering oversized payloads into RAM.
    Rejects early if reported content length exceeds max_bytes.
    """
    # 1. Early rejection based on file.size (Content-Length header)
    if file.size is not None and file.size > max_bytes:
        max_mb = max_bytes // (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"File size exceeds maximum allowed limit of {max_mb}MB."
        )

    # 2. Chunked stream reading
    content = bytearray()
    chunk_size = 64 * 1024  # 64 KB chunks
    try:
        await file.seek(0)
    except Exception:
        pass

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        content.extend(chunk)
        if len(content) > max_bytes:
            max_mb = max_bytes // (1024 * 1024)
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed limit of {max_mb}MB."
            )

    return bytes(content)


async def process_cv(
    file: UploadFile,
    user_id: Optional[int] = None,
    max_size_bytes: Optional[int] = None
) -> dict:
    """
    Processes an uploaded CV PDF file:
    1. Validates that the file has a PDF extension and MIME type.
    2. Enforces configurable upload size limit (default 10 MB).
    3. Rejects empty files or files lacking standard %PDF- header magic bytes.
    4. Saves the file using persistent storage backend (local disk or private S3).
    5. Extracts text across all pages using pdf_service.
    6. Returns structured JSON containing filename, file_path, page count, and full text.
    """
    filename = file.filename or ""

    # Validate file format (check MIME type or extension)
    is_pdf_mime = file.content_type in ["application/pdf", "application/x-pdf", "binary/octet-stream"]
    is_pdf_ext = filename.lower().endswith(".pdf")

    if not (is_pdf_mime or is_pdf_ext) or (not is_pdf_ext and file.content_type not in ["application/pdf", "application/x-pdf"]):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    # Read uploaded file content with strict size boundary enforcement
    limit = max_size_bytes or get_max_upload_size_bytes()
    content = await read_bounded_file(file, limit)

    if not content or len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty."
        )

    # Reject non-PDF or corrupted files lacking magic bytes signature
    if not (content.startswith(b"%PDF") or b"%PDF" in content[:1024]):
        raise HTTPException(
            status_code=400,
            detail="Invalid PDF file: Missing %PDF signature header."
        )

    # Save file via storage abstraction
    storage = get_storage_backend()
    storage_key, file_path = storage.save_file(content, filename, user_id=user_id)

    # Extract text from PDF
    # If storage path exists locally, extract directly; otherwise retrieve bytes
    if os.path.exists(file_path):
        pdf_data = extract_pdf_text(file_path)
    else:
        # For non-local storage (e.g. S3), write to temporary local scratch file for parsing
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            pdf_data = extract_pdf_text(tmp_path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except OSError:
                    pass

    return {
        "filename": file.filename,
        "file_path": file_path,
        "storage_key": storage_key,
        "pages": pdf_data["pages"],
        "text": pdf_data["text"],
        "parsing_method": pdf_data.get("parsing_method", "unknown"),
        "parse_quality_score": pdf_data.get("parse_quality_score", 0.0)
    }