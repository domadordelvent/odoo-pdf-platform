import unittest
from io import BytesIO

from pypdf import PdfReader

from pdf_engine.exceptions import PdfEngineError
from pdf_engine.merger import merge_pdfs
from tests.pdf_helpers import make_pdf


class MergePdfsTests(unittest.TestCase):
    def test_multiple_pdfs_preserve_page_count_and_order(self):
        inputs = [make_pdf([72, 144]), make_pdf([216]), make_pdf([288, 360])]

        result = merge_pdfs(inputs)

        self.assertIsInstance(result, bytes)
        reader = PdfReader(BytesIO(result))
        self.assertEqual(len(reader.pages), 5)
        self.assertEqual(
            [float(page.mediabox.width) for page in reader.pages],
            [72, 144, 216, 288, 360],
        )

    def test_empty_password_input_is_accepted(self):
        result = merge_pdfs([make_pdf([72]), make_pdf([144, 216], password="")])

        reader = PdfReader(BytesIO(result))
        self.assertEqual(len(reader.pages), 3)
        self.assertEqual(
            [float(page.mediabox.width) for page in reader.pages],
            [72, 144, 216],
        )

    def test_invalid_input_propagates_engine_error(self):
        invalid_inputs = {
            "empty": b"",
            "non_pdf": b"This is not a PDF.",
            "truncated": make_pdf()[:32],
            "zero_pages": make_pdf([]),
            "password_required": make_pdf(password="secret"),
        }
        for name, invalid in invalid_inputs.items():
            for position in range(3):
                with self.subTest(invalid=name, position=position):
                    inputs = [make_pdf([72]), make_pdf([144])]
                    inputs.insert(position, invalid)
                    with self.assertRaises(PdfEngineError):
                        merge_pdfs(inputs)


if __name__ == "__main__":
    unittest.main()
