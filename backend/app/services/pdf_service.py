from pypdf import PdfReader
from fastapi import HTTPException


def extract_pdf_text(file_path: str) -> dict:
    """
    Extracts text from all pages of a PDF file.
    Returns dictionary with page count and extracted text.
    """
    try:
        reader = PdfReader(file_path)
        total_pages = len(reader.pages)

        if total_pages == 0:
            raise HTTPException(
                status_code=400,
                detail="PDF file contains no pages."
            )

        page_texts = []
        for index, page in enumerate(reader.pages):
            extracted = page.extract_text() or ""
            page_texts.append(extracted.strip())

        full_text = "\n\n".join(page_texts).strip()

        return {
            "pages": total_pages,
            "text": full_text
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not parse PDF file: {str(e)}"
        )