import unittest
from io import BytesIO

from pypdf import PdfReader
from reportlab.pdfgen import canvas

from pdf_engine.exceptions import PdfEngineError
from pdf_engine.watermark import add_watermark
from tests.pdf_helpers import make_pdf


class AddWatermarkTests(unittest.TestCase):
    def test_watermark_preserves_page_count_order_and_dimensions(self):
        result = add_watermark(make_pdf([72, 144, 216]), "DRAFT")

        self.assertIsInstance(result, bytes)
        reader = PdfReader(BytesIO(result))
        self.assertEqual(len(reader.pages), 3)
        self.assertEqual(
            [float(page.mediabox.width) for page in reader.pages],
            [72, 144, 216],
        )
        self.assertEqual(
            [float(page.mediabox.height) for page in reader.pages],
            [300, 300, 300],
        )
        for page in reader.pages:
            self.assertIn("DRAFT", page.extract_text())

    def test_existing_content_is_preserved_on_each_page(self):
        source = BytesIO()
        pdf = canvas.Canvas(source)
        sizes = ((300, 400), (500, 200))
        for index, size in enumerate(sizes, start=1):
            pdf.setPageSize(size)
            pdf.drawString(20, 30, f"Original page {index}")
            pdf.showPage()
        pdf.save()

        result = add_watermark(source.getvalue(), "CONFIDENTIAL")

        reader = PdfReader(BytesIO(result))
        self.assertEqual(len(reader.pages), 2)
        for index, (page, size) in enumerate(zip(reader.pages, sizes), start=1):
            self.assertEqual(
                (float(page.mediabox.width), float(page.mediabox.height)), size
            )
            self.assertIn(f"Original page {index}", page.extract_text())
            self.assertIn("CONFIDENTIAL", page.extract_text())

    def test_empty_text_preserves_engine_behavior(self):
        result = add_watermark(make_pdf([144]), "")

        reader = PdfReader(BytesIO(result))
        self.assertEqual(len(reader.pages), 1)
        self.assertEqual(float(reader.pages[0].mediabox.width), 144)
        self.assertEqual(reader.pages[0].extract_text().strip(), "")

    def test_empty_password_input_is_accepted(self):
        result = add_watermark(make_pdf([72, 144], password=""), "DRAFT")

        reader = PdfReader(BytesIO(result))
        self.assertEqual(len(reader.pages), 2)
        self.assertEqual(
            [float(page.mediabox.width) for page in reader.pages], [72, 144]
        )
        for page in reader.pages:
            self.assertIn("DRAFT", page.extract_text())

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
                    add_watermark(invalid, "DRAFT")


if __name__ == "__main__":
    unittest.main()
