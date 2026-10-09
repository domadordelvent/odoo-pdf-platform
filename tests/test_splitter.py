import unittest
from io import BytesIO

from pypdf import PdfReader

from pdf_engine.exceptions import PdfEngineError
from pdf_engine.splitter import split_pdf
from tests.pdf_helpers import make_pdf


class SplitPdfTests(unittest.TestCase):
    def test_split_preserves_page_count_and_order(self):
        pdf = make_pdf([72, 144, 216])

        outputs = split_pdf(pdf)

        self.assertEqual(len(outputs), 3)
        self.assertEqual(
            [output["page"] for output in outputs],
            [1, 2, 3],
        )

        widths = []
        for output in outputs:
            reader = PdfReader(BytesIO(output["data"]))
            widths.append(float(reader.pages[0].mediabox.width))

        self.assertEqual(widths, [72, 144, 216])

    def test_invalid_input_raises_engine_error(self):
        with self.assertRaises(PdfEngineError):
            split_pdf(b"not a pdf")


if __name__ == "__main__":
    unittest.main()