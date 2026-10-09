import unittest

from pypdf import PdfReader

from pdf_engine.exceptions import PdfEngineError
from pdf_engine.validator import validate_pdf
from tests.pdf_helpers import make_pdf


class ValidatePdfTests(unittest.TestCase):
    def test_valid_pdf_returns_usable_reader(self):
        reader = validate_pdf(make_pdf([72, 144]))

        self.assertIsInstance(reader, PdfReader)
        self.assertEqual(len(reader.pages), 2)
        self.assertEqual([float(page.mediabox.width) for page in reader.pages], [72, 144])

    def test_empty_password_is_accepted(self):
        reader = validate_pdf(make_pdf([144], password=""))

        self.assertIsInstance(reader, PdfReader)
        self.assertEqual(len(reader.pages), 1)
        self.assertEqual(float(reader.pages[0].mediabox.width), 144)

    def test_empty_bytes_are_rejected(self):
        with self.assertRaises(PdfEngineError):
            validate_pdf(b"")

    def test_non_pdf_is_rejected(self):
        with self.assertRaises(PdfEngineError):
            validate_pdf(b"This is not a PDF.")

    def test_truncated_pdf_is_rejected(self):
        # Keep the header but remove the page tree, cross-reference and trailer.
        with self.assertRaises(PdfEngineError):
            validate_pdf(make_pdf()[:32])

    def test_zero_pages_are_rejected(self):
        with self.assertRaises(PdfEngineError):
            validate_pdf(make_pdf([]))

    def test_required_password_is_rejected(self):
        with self.assertRaises(PdfEngineError):
            validate_pdf(make_pdf(password="secret"))


if __name__ == "__main__":
    unittest.main()
