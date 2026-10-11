import io
import re
import logging
from typing import Tuple, Optional
from fastapi import HTTPException

logger = logging.getLogger(__name__)


def is_usable_text(text: Optional[str]) -> Tuple[bool, float]:
    """
    Evaluates whether extracted text is usable:
    - If length < 300 characters, accepts it when at least 50 characters of real words exist;
      only rejects empty or garbled text.
    - If length >= 300 characters, requires density > 0.5 and at least 50 characters of real words.
    Returns (is_usable, quality_score).
    """
    if not text or not text.strip():
        return False, 0.0

    clean_text = text.strip()
    total_len = len(clean_text)
    if total_len == 0:
        return False, 0.0

    # Count alphanumeric characters and density
    alpha_count = sum(c.isalnum() for c in clean_text)
    density = alpha_count / total_len

    # Identify real words (sequences of 2+ alphabetic characters)
    real_words = re.findall(r'[a-zA-Z]{2,}', clean_text)
    real_word_chars = sum(len(w) for w in real_words)

    # Reject garbled text (severe lack of alphanumeric characters)
    if density < 0.4:
        return False, round(density, 2)

    if total_len < 300:
        # Under 300 characters: accept when at least 50 characters of real words exist
        if real_word_chars >= 50:
            quality = min(1.0, max(density, real_word_chars / 300.0))
            return True, round(quality, 2)
        return False, round(density, 2)
    else:
        # 300+ characters: accept when density > 0.5 and real word content exists
        if density > 0.5 and real_word_chars >= 50:
            return True, round(min(1.0, density), 2)
        return False, round(density, 2)


def _extract_pymupdf(file_path: str) -> str:
    try:
        import fitz
        doc = fitz.open(file_path)
        if len(doc) == 0:
            return ""
        text = ""
        for page in doc:
            text += page.get_text("text") + "\n\n"
        return text.strip()
    except Exception as e:
        logger.debug(f"PyMuPDF extract failed: {e}")
        return ""


def _extract_pdfplumber(file_path: str) -> str:
    try:
        import pdfplumber
        text = ""
        with pdfplumber.open(file_path) as pdf:
            if len(pdf.pages) == 0:
                return ""
            for page in pdf.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n\n"
        return text.strip()
    except Exception as e:
        logger.debug(f"pdfplumber extract failed: {e}")
        return ""


def _extract_ocr(file_path: str) -> str:
    """
    Extracts text using OCR. Silently catches missing dependencies (poppler/tesseract)
    or other failures and returns empty string.
    """
    try:
        from pdf2image import convert_from_path
        import pytesseract
        images = convert_from_path(file_path)
        text = ""
        for img in images:
            text += pytesseract.image_to_string(img) + "\n\n"
        return text.strip()
    except Exception as e:
        # Silently skip OCR if dependencies (poppler/tesseract) are missing
        logger.debug(f"OCR skipped or failed: {e}")
        return ""


def extract_pdf_text(file_path: str) -> dict:
    """
    Extracts text from all pages of a PDF file using multiple methods:
    1. PyMuPDF (fitz)
    2. pdfplumber
    3. OCR fallback (pdf2image + pytesseract)

    Returns dictionary with text, parsing_method, and parse_quality_score.
    Raises HTTPException(400) if no usable text can be extracted.
    """
    text = ""
    method_used = "none"
    parse_quality = 0.0

    methods = [
        ("pymupdf", _extract_pymupdf),
        ("pdfplumber", _extract_pdfplumber),
        ("ocr", _extract_ocr)
    ]

    for name, func in methods:
        try:
            candidate_text = func(file_path)
            is_usable, quality = is_usable_text(candidate_text)
            if is_usable:
                text = candidate_text
                method_used = name
                parse_quality = quality
                break
        except Exception as e:
            logger.warning(f"Parse method {name} failed on {file_path}: {e}")

    if not text:
        raise HTTPException(
            status_code=400,
            detail="We couldn't read text from this PDF. If it's a scan, export a text-based PDF."
        )

    return {
        "text": text,
        "parsing_method": method_used,
        "parse_quality_score": round(parse_quality, 2),
        "pages": 1
    }