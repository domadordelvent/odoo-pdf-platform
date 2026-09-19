import subprocess
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader

from pdf_engine.compressor import compress_pdf
from pdf_engine.exceptions import PdfEngineError
from tests.pdf_helpers import make_pdf


class CompressPdfTests(unittest.TestCase):
    def test_all_profiles_preserve_page_count_order_and_dimensions(self):
        for level in ("low", "medium", "high"):
            with self.subTest(level=level):
                result = compress_pdf(make_pdf([72, 144, 216]), level)

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

    def test_empty_password_input_is_passed_unchanged_to_ghostscript(self):
        source = make_pdf([72, 144], password="")
        expected_output = make_pdf([72, 144])

        def run(command, **kwargs):
            self.assertEqual(Path(command[-1]).read_bytes(), source)
            Path(command[-2].split("=", 1)[1]).write_bytes(expected_output)

        with patch("pdf_engine.compressor.subprocess.run", side_effect=run) as mocked_run:
            self.assertEqual(compress_pdf(source, "medium"), expected_output)
            mocked_run.assert_called_once()

    def test_unsupported_level_is_rejected_before_pdf_validation(self):
        for level in ("invalid", "", None):
            with self.subTest(level=level):
                with patch("pdf_engine.compressor.subprocess.run") as run:
                    with self.assertRaises(PdfEngineError) as error:
                        compress_pdf(b"", level)
                    self.assertEqual(
                        str(error.exception), f"Unsupported compression level: {level}"
                    )
                    run.assert_not_called()

    def test_invalid_input_is_rejected_before_ghostscript(self):
        invalid_inputs = {
            "empty": b"",
            "non_pdf": b"This is not a PDF.",
            "truncated": make_pdf()[:32],
            "zero_pages": make_pdf([]),
            "password_required": make_pdf(password="secret"),
        }
        for name, invalid in invalid_inputs.items():
            with self.subTest(invalid=name):
                with patch("pdf_engine.compressor.subprocess.run") as run:
                    with self.assertRaises(PdfEngineError):
                        compress_pdf(invalid, "medium")
                    run.assert_not_called()

    def test_command_profiles_original_input_and_output_are_preserved(self):
        source = make_pdf([72])
        expected_output = make_pdf([144])
        for level, profile in (("low", "/printer"), ("medium", "/ebook"), ("high", "/screen")):
            with self.subTest(level=level):
                paths = []

                def run(command, **kwargs):
                    input_path = Path(command[-1])
                    output_path = Path(command[-2].split("=", 1)[1])
                    paths.extend([input_path, output_path])
                    self.assertEqual(input_path.read_bytes(), source)
                    self.assertEqual(command[:-2], [
                        "gs", "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
                        f"-dPDFSETTINGS={profile}", "-dNOPAUSE", "-dQUIET", "-dBATCH",
                    ])
                    self.assertEqual(kwargs, dict(check=True, capture_output=True, text=True))
                    output_path.write_bytes(expected_output)

                with patch("pdf_engine.compressor.subprocess.run", side_effect=run):
                    self.assertEqual(compress_pdf(source, level), expected_output)
                self.assertTrue(all(not path.exists() for path in paths))

    def test_missing_ghostscript_preserves_error(self):
        cause = FileNotFoundError("gs")
        with patch("pdf_engine.compressor.subprocess.run", side_effect=cause):
            with self.assertRaises(PdfEngineError) as error:
                compress_pdf(make_pdf(), "medium")
        self.assertEqual(str(error.exception), "Ghostscript executable was not found.")
        self.assertIs(error.exception.__cause__, cause)

    def test_ghostscript_failure_preserves_error_details(self):
        cases = (
            (" stderr detail ", "stdout detail", "stderr detail"),
            ("  ", " stdout detail ", "stdout detail"),
            ("", "", "Unknown Ghostscript error."),
        )
        for stderr, stdout, expected in cases:
            with self.subTest(expected=expected):
                cause = subprocess.CalledProcessError(1, "gs", output=stdout, stderr=stderr)
                with patch("pdf_engine.compressor.subprocess.run", side_effect=cause):
                    with self.assertRaises(PdfEngineError) as error:
                        compress_pdf(make_pdf(), "medium")
                self.assertEqual(
                    str(error.exception), f"Ghostscript compression failed: {expected}"
                )
                self.assertIs(error.exception.__cause__, cause)

    def test_missing_output_preserves_error(self):
        with patch("pdf_engine.compressor.subprocess.run"):
            with self.assertRaises(PdfEngineError) as error:
                compress_pdf(make_pdf(), "medium")
        self.assertEqual(
            str(error.exception),
            "Ghostscript compression failed: no output PDF was created.",
        )


if __name__ == "__main__":
    unittest.main()
