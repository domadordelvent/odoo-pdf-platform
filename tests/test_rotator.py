import unittest
from io import BytesIO

from pypdf import PdfReader, PdfWriter

from pdf_engine.exceptions import PdfEngineError
from pdf_engine.rotator import rotate_pdf
from tests.pdf_helpers import make_pdf


class RotatePdfTests(unittest.TestCase):
    def test_rotation_preserves_page_count_order_and_dimensions(self):
        for angle in (0, 90, 180, 270, -90, 450):
            with self.subTest(angle=angle):
                result = rotate_pdf(make_pdf([72, 144, 216]), angle)

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
                self.assertEqual(
                    [page.rotation for page in reader.pages],
                    [angle] * 3,
                )

    def test_rotation_adds_to_existing_page_rotation(self):
        reader = PdfReader(BytesIO(make_pdf([72, 144])))
        writer = PdfWriter()
        for page, angle in zip(reader.pages, (90, 270)):
            page.rotate(angle)
            writer.add_page(page)
        source = BytesIO()
        writer.write(source)

        result = rotate_pdf(source.getvalue(), 90)

        rotated = PdfReader(BytesIO(result))
        self.assertEqual([page.rotation for page in rotated.pages], [180, 360])

    def test_invalid_angle_preserves_value_error(self):
        for angle in (45, -45, 91):
            with self.subTest(angle=angle):
                with self.assertRaises(ValueError):
                    rotate_pdf(make_pdf(), angle)

    def test_empty_password_input_is_accepted(self):
        result = rotate_pdf(make_pdf([72, 144], password=""), 90)

        reader = PdfReader(BytesIO(result))
        self.assertEqual(len(reader.pages), 2)
        self.assertEqual([page.rotation for page in reader.pages], [90, 90])
        self.assertEqual(
            [float(page.mediabox.width) for page in reader.pages], [72, 144]
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
                    rotate_pdf(invalid, 90)


if __name__ == "__main__":
    unittest.main()
