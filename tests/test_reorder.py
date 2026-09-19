import unittest
from io import BytesIO

from pypdf import PdfReader

from pdf_engine.exceptions import PdfEngineError
from pdf_engine.reorder import reorder_pages
from tests.pdf_helpers import make_pdf


class ReorderPagesTests(unittest.TestCase):
    def test_reorder_preserves_page_count_and_dimensions(self):
        orders = {
            "3,1,2": [216, 72, 144],
            " 3, 1-2 ": [216, 72, 144],
            "1-3": [72, 144, 216],
            "3,2,1": [216, 144, 72],
            "3-1,1-3": [72, 144, 216],
        }
        for order, widths in orders.items():
            with self.subTest(order=order):
                result = reorder_pages(make_pdf([72, 144, 216]), order)

                self.assertIsInstance(result, bytes)
                reader = PdfReader(BytesIO(result))
                self.assertEqual(len(reader.pages), 3)
                self.assertEqual(
                    [float(page.mediabox.width) for page in reader.pages], widths
                )
                self.assertEqual(
                    [float(page.mediabox.height) for page in reader.pages],
                    [300, 300, 300],
                )

    def test_single_page_is_accepted(self):
        result = reorder_pages(make_pdf([144]), "1")

        reader = PdfReader(BytesIO(result))
        self.assertEqual(len(reader.pages), 1)
        self.assertEqual(float(reader.pages[0].mediabox.width), 144)

    def test_invalid_permutations_preserve_value_error_and_message(self):
        orders = ("1,2", "1,1,3", "1,2,3,3", "0,1,2", "1,2,4", "1-4", "3-1")
        for order in orders:
            with self.subTest(order=order):
                with self.assertRaises(ValueError) as error:
                    reorder_pages(make_pdf([72, 144, 216]), order)
                self.assertEqual(
                    str(error.exception),
                    "Reorder requires all pages exactly once. Expected pages: 1-3",
                )

    def test_malformed_order_preserves_value_error(self):
        for order in ("", "abc", "1,", "1-", "1-2-3", "-1"):
            with self.subTest(order=order):
                with self.assertRaises(ValueError):
                    reorder_pages(make_pdf([72, 144, 216]), order)

    def test_empty_password_input_is_accepted(self):
        result = reorder_pages(make_pdf([72, 144], password=""), "2,1")

        reader = PdfReader(BytesIO(result))
        self.assertEqual(len(reader.pages), 2)
        self.assertEqual(
            [float(page.mediabox.width) for page in reader.pages], [144, 72]
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
                    reorder_pages(invalid, "1")


if __name__ == "__main__":
    unittest.main()
