import os
import uuid

from fastapi import UploadFile, HTTPException

from .pdf_service import extract_pdf_text


async def process_cv(file: UploadFile) -> dict:
    """
    Processes an uploaded CV PDF file:
    1. Validates that the file is a PDF.
    2. Saves the file to uploads storage.
    3. Extracts text across all pages.
    4. Returns structured JSON containing filename, page count, and full text.
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

    # Read uploaded file content
    content = await file.read()

    if not content or len(content) == 0:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty."
        )

    # Ensure uploads directory exists
    os.makedirs("uploads", exist_ok=True)

    # Generate unique storage filename
    file_id = str(uuid.uuid4())
    file_path = os.path.join("uploads", f"{file_id}.pdf")

    with open(file_path, "wb") as f:
        f.write(content)

    # Extract text from PDF
    pdf_data = extract_pdf_text(file_path)

    return {
        "filename": file.filename,
        "file_path": file_path,
        "pages": pdf_data["pages"],
        "text": pdf_data["text"]
    }