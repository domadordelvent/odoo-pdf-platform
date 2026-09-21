import subprocess
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject
from reportlab.pdfgen import canvas

from pdf_engine.compressor import GHOSTSCRIPT_TIMEOUT_SECONDS, compress_pdf
from pdf_engine.exceptions import PdfEngineError
from tests.pdf_helpers import make_pdf
from pdf_engine.validator import validate_pdf


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

    def test_empty_password_pdf_preserves_visible_text_with_real_ghostscript(self):
        source = BytesIO()
        pdf = canvas.Canvas(source, pagesize=(300, 400))
        texts = ("First page original content", "Second page original content")
        for text in texts:
            pdf.drawString(30, 200, text)
            pdf.showPage()
        pdf.save()
        reader = PdfReader(BytesIO(source.getvalue()))
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)
        writer.encrypt("")
        encrypted = BytesIO()
        writer.write(encrypted)
        self.assertTrue(PdfReader(BytesIO(encrypted.getvalue())).is_encrypted)

        for level in ("low", "medium", "high"):
            with self.subTest(level=level):
                result = compress_pdf(encrypted.getvalue(), level)

                reader = PdfReader(BytesIO(result))
                self.assertFalse(reader.is_encrypted)
                self.assertEqual(len(reader.pages), 2)
                for page, text in zip(reader.pages, texts):
                    self.assertEqual(page.extract_text().strip(), text)
                    self.assertEqual(float(page.mediabox.width), 300)
                    self.assertEqual(float(page.mediabox.height), 400)

    def test_page_drawing_error_with_real_ghostscript_is_rejected(self):
        writer = PdfWriter()
        page = writer.add_blank_page(width=300, height=400)
        content = DecodedStreamObject()
        # An unresolved image draw produces a blank PDF with exit status zero.
        content.set_data(b"q 100 0 0 100 30 30 cm /MissingImage Do")
        page[NameObject("/Contents")] = writer._add_object(content)
        source = BytesIO()
        writer.write(source)
        validate_pdf(source.getvalue())
        real_run = subprocess.run

        for level in ("low", "medium", "high"):
            with self.subTest(level=level):
                paths = []

                def run(command, **kwargs):
                    result = real_run(command, **kwargs)
                    self.assertEqual(result.returncode, 0)
                    self.assertIn("Page drawing error", result.stdout + result.stderr)
                    output_path = Path(command[-2].split("=", 1)[1])
                    paths.extend([Path(command[-1]), output_path, output_path.parent])
                    reader = validate_pdf(output_path.read_bytes())
                    self.assertEqual(len(reader.pages), 1)
                    self.assertEqual(reader.pages[0].extract_text(), "")
                    self.assertFalse(reader.pages[0].images)
                    return result

                with patch("pdf_engine.compressor.subprocess.run", side_effect=run):
                    with self.assertRaisesRegex(PdfEngineError, "Page drawing error"):
                        compress_pdf(source.getvalue(), level)
                self.assertTrue(all(not path.exists() for path in paths))

    def test_page_drawing_diagnostics_are_rejected_on_either_stream(self):
        diagnostic = "   **** Error: Page drawing error occurred.\nOutput may be incorrect."
        for stdout, stderr in ((diagnostic, ""), ("", diagnostic)):
            with self.subTest(stdout=stdout, stderr=stderr):
                def run(command, **kwargs):
                    Path(command[-2].split("=", 1)[1]).write_bytes(make_pdf())
                    return subprocess.CompletedProcess(command, 0, stdout, stderr)

                with patch("pdf_engine.compressor.subprocess.run", side_effect=run):
                    with self.assertRaisesRegex(PdfEngineError, "Page drawing error"):
                        compress_pdf(make_pdf(), "medium")

    def test_harmless_ghostscript_warnings_are_accepted(self):
        expected = make_pdf()
        warning = "Warning: substituting font Helvetica.\nThe file was repaired."
        for stdout, stderr in ((warning, ""), ("", warning), ("", "")):
            with self.subTest(stdout=stdout, stderr=stderr):
                def run(command, **kwargs):
                    Path(command[-2].split("=", 1)[1]).write_bytes(expected)
                    return subprocess.CompletedProcess(command, 0, stdout, stderr)

                with patch("pdf_engine.compressor.subprocess.run", side_effect=run):
                    self.assertEqual(compress_pdf(make_pdf(), "medium"), expected)

    def test_invalid_ghostscript_output_is_rejected(self):
        invalid_outputs = {
            "empty": b"",
            "non_pdf": b"not a PDF",
            "truncated": make_pdf()[:32],
            "zero_pages": make_pdf([]),
        }
        for name, output in invalid_outputs.items():
            with self.subTest(output=name):
                paths = []

                def run(command, **kwargs):
                    output_path = Path(command[-2].split("=", 1)[1])
                    paths.append(output_path)
                    output_path.write_bytes(output)
                    return subprocess.CompletedProcess(command, 0, "", "")

                with patch("pdf_engine.compressor.subprocess.run", side_effect=run):
                    with self.assertRaises(PdfEngineError):
                        compress_pdf(make_pdf(), "medium")
                self.assertTrue(all(not path.exists() for path in paths))

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
                    self.assertEqual(kwargs, dict(check=True, capture_output=True, text=True, timeout=GHOSTSCRIPT_TIMEOUT_SECONDS))
                    output_path.write_bytes(expected_output)
                    return subprocess.CompletedProcess(command, 0, "", "")

                with patch("pdf_engine.compressor.subprocess.run", side_effect=run):
                    self.assertEqual(compress_pdf(source, level), expected_output)
                self.assertTrue(all(not path.exists() for path in paths))

    def test_timeout_raises_engine_error_and_cleans_temporary_files(self):
        paths = []
        cause = subprocess.TimeoutExpired("gs", GHOSTSCRIPT_TIMEOUT_SECONDS)

        def run(command, **kwargs):
            self.assertEqual(kwargs["timeout"], GHOSTSCRIPT_TIMEOUT_SECONDS)
            input_path = Path(command[-1])
            output_path = Path(command[-2].split("=", 1)[1])
            self.assertTrue(input_path.is_file())
            output_path.write_bytes(b"partial output")
            paths.extend([input_path, output_path, input_path.parent])
            raise cause

        with patch("pdf_engine.compressor.subprocess.run", side_effect=run):
            with self.assertRaises(PdfEngineError) as error:
                compress_pdf(make_pdf(), "medium")
        self.assertEqual(
            str(error.exception),
            f"Ghostscript compression timed out after {GHOSTSCRIPT_TIMEOUT_SECONDS} seconds.",
        )
        self.assertIs(error.exception.__cause__, cause)
        self.assertEqual(len(paths), 3)
        self.assertTrue(all(not path.exists() for path in paths))

    def test_subprocess_failures_clean_temporary_files(self):
        causes = (
            FileNotFoundError("gs"),
            subprocess.CalledProcessError(1, "gs", output="", stderr="Failed"),
        )
        for cause in causes:
            with self.subTest(error=type(cause).__name__):
                paths = []

                def run(command, **kwargs):
                    input_path = Path(command[-1])
                    output_path = Path(command[-2].split("=", 1)[1])
                    self.assertTrue(input_path.is_file())
                    if isinstance(cause, subprocess.CalledProcessError):
                        output_path.write_bytes(b"partial output")
                    paths.extend([input_path, output_path, input_path.parent])
                    raise cause

                with patch("pdf_engine.compressor.subprocess.run", side_effect=run):
                    with self.assertRaises(PdfEngineError) as error:
                        compress_pdf(make_pdf(), "medium")
                self.assertIs(error.exception.__cause__, cause)
                self.assertEqual(len(paths), 3)
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
        with patch("pdf_engine.compressor.subprocess.run", return_value=subprocess.CompletedProcess("gs", 0, "", "")):
            with self.assertRaises(PdfEngineError) as error:
                compress_pdf(make_pdf(), "medium")
        self.assertEqual(
            str(error.exception),
            "Ghostscript compression failed: no output PDF was created.",
        )


if __name__ == "__main__":
    unittest.main()
