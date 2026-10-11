import os
import tempfile
import unittest
from unittest.mock import patch
import fitz
from fastapi import HTTPException

from app.services.pdf_service import extract_pdf_text, is_usable_text


class TestPdfProcessing(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_text_pdf(self, text: str) -> str:
        """Helper to create a temporary PDF with given text content."""
        pdf_path = os.path.join(self.temp_dir.name, "test_doc.pdf")
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((50, 72), text, fontsize=12)
        doc.save(pdf_path)
        doc.close()
        return pdf_path

    def _create_image_only_pdf(self) -> str:
        """Helper to create a temporary PDF containing only an image (no selectable text)."""
        pdf_path = os.path.join(self.temp_dir.name, "image_only.pdf")
        doc = fitz.open()
        page = doc.new_page(width=300, height=300)
        # 1x1 PNG bytes
        png_bytes = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00"
            b"\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        rect = fitz.Rect(50, 50, 250, 250)
        page.insert_image(rect, stream=png_bytes)
        doc.save(pdf_path)
        doc.close()
        return pdf_path

    def test_short_cv_accepted_under_300_chars_with_50_real_words(self):
        """
        If text extraction returns usable text under 300 characters,
        accept it when at least 50 characters of real words exist.
        """
        short_text = (
            "Alex Smith\n"
            "Full Stack Developer skilled in Python, SQL, and Docker containerization.\n"
            "Built web applications."
        )
        self.assertLess(len(short_text), 300)
        usable, quality = is_usable_text(short_text)
        self.assertTrue(usable)
        self.assertGreater(quality, 0.0)

        # Create actual PDF and test extraction
        pdf_path = self._create_text_pdf(short_text)
        res = extract_pdf_text(pdf_path)

        self.assertIn("Python", res["text"])
        self.assertIn("Docker", res["text"])
        self.assertGreaterEqual(res["parse_quality_score"], 0.4)
        self.assertIn(res["parsing_method"], ["pymupdf", "pdfplumber"])

    def test_short_cv_rejected_when_real_words_under_50_characters(self):
        """Short text with less than 50 characters of real words is rejected as insufficient/garbled."""
        sparse_text = "CV: John. A B C."
        self.assertLess(len(sparse_text), 300)
        usable, _ = is_usable_text(sparse_text)
        self.assertFalse(usable)

        pdf_path = self._create_text_pdf(sparse_text)
        with self.assertRaises(HTTPException) as ctx:
            extract_pdf_text(pdf_path)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(
            ctx.exception.detail,
            "We couldn't read text from this PDF. If it's a scan, export a text-based PDF."
        )

    def test_garbled_text_rejected(self):
        """Garbled text with random punctuation/symbols is rejected."""
        garbled = "@#$%^&*()_+~`|}{[]:;?><,./ 12345 @#$%^&*"
        usable, _ = is_usable_text(garbled)
        self.assertFalse(usable)

    def test_image_only_pdf_missing_ocr_dependencies_returns_clean_400(self):
        """
        When an image-only PDF has no text layer and OCR dependencies (poppler/tesseract)
        are missing, OCR is skipped silently and HTTP 400 is returned with clear message.
        Never mentions poppler to the user.
        """
        pdf_path = self._create_image_only_pdf()

        # Simulate missing OCR dependencies (e.g. FileNotFoundError when calling poppler / tesseract)
        with patch("app.services.pdf_service._extract_ocr") as mock_ocr:
            mock_ocr.return_value = ""

            with self.assertRaises(HTTPException) as ctx:
                extract_pdf_text(pdf_path)

            self.assertEqual(ctx.exception.status_code, 400)
            self.assertEqual(
                ctx.exception.detail,
                "We couldn't read text from this PDF. If it's a scan, export a text-based PDF."
            )
            # Crucial check: never mention poppler to the user
            self.assertNotIn("poppler", ctx.exception.detail.lower())
            self.assertNotIn("tesseract", ctx.exception.detail.lower())

    def test_image_only_pdf_ocr_exception_handled_silently(self):
        """
        If pdf2image raises PDFInfoNotInstalledError or FileNotFoundError (missing poppler),
        the error is caught silently in _extract_ocr and does not crash with 500.
        """
        from app.services.pdf_service import _extract_ocr

        with patch("pdf2image.convert_from_path", side_effect=FileNotFoundError("Unable to get page count. Is poppler installed and in PATH?")):
            # Must return "" without re-raising exception
            res = _extract_ocr("dummy_path.pdf")
            self.assertEqual(res, "")


if __name__ == "__main__":
    unittest.main()
