import unittest
from io import BytesIO

from pypdf import PdfReader

from pdf_engine.exceptions import PdfEngineError
from pdf_engine.extractor import extract_pages
from tests.pdf_helpers import make_pdf


class ExtractPagesTests(unittest.TestCase):
    def test_selection_preserves_order_duplicates_and_dimensions(self):
        result = extract_pages(make_pdf([72, 144, 216, 288]), " 4, 2-3, 2, 1 ")

        self.assertIsInstance(result, bytes)
        reader = PdfReader(BytesIO(result))
        self.assertEqual(len(reader.pages), 5)
        self.assertEqual(
            [float(page.mediabox.width) for page in reader.pages],
            [288, 144, 216, 144, 72],
        )
        self.assertEqual(
            [float(page.mediabox.height) for page in reader.pages],
            [300] * 5,
        )

    def test_nonexistent_pages_preserve_value_error_and_message(self):
        for selection, missing in (("0", 0), ("4", 4), ("2-4", 4)):
            with self.subTest(selection=selection):
                with self.assertRaises(ValueError) as error:
                    extract_pages(make_pdf([72, 144, 216]), selection)
                self.assertEqual(str(error.exception), f"Page {missing} does not exist.")

    def test_malformed_selection_preserves_value_error(self):
        for selection in ("", "abc", "1,", "1-", "1-2-3", "-1"):
            with self.subTest(selection=selection):
                with self.assertRaises(ValueError):
                    extract_pages(make_pdf([72, 144, 216]), selection)

    def test_descending_range_preserves_empty_output(self):
        result = extract_pages(make_pdf([72, 144, 216]), "3-1")

        self.assertIsInstance(result, bytes)
        self.assertEqual(len(PdfReader(BytesIO(result)).pages), 0)

    def test_empty_password_input_is_accepted(self):
        result = extract_pages(make_pdf([72, 144, 216], password=""), "3,1")

        reader = PdfReader(BytesIO(result))
        self.assertEqual(len(reader.pages), 2)
        self.assertEqual(
            [float(page.mediabox.width) for page in reader.pages], [216, 72]
        )

    def test_invalid_input_raises_engine_error(self):
        invalid_inputs = {
            "empty": b"",
            "non_pdf": b"This is not a PDF.",
            "truncated": make_pdf()[:32],
            "zero_pages": make_pdf([]),
            "password_required": make_pdf(password="secret"),
        }
        for name, invalid in invalid_inputs.items():
            with self.subTest(invalid=name):
                with self.assertRaises(PdfEngineError):
                    extract_pages(invalid, "1")


if __name__ == "__main__":
    unittest.main()
