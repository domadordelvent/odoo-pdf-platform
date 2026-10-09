import unittest
from unittest.mock import Mock, patch
from io import BytesIO
from pypdf import PdfReader

from pdf_engine import limits
from pdf_engine.exceptions import PdfEngineError
from pdf_engine.validator import validate_pdf
from pdf_engine.merger import merge_pdfs
from pdf_engine.extractor import extract_pages
from pdf_engine.reorder import reorder_pages
from pdf_engine.splitter import split_pdf
from pdf_engine.rotator import rotate_pdf
from pdf_engine.watermark import add_watermark
from pdf_engine.compressor import compress_pdf
from tests.pdf_helpers import make_pdf


class ResourceLimitTests(unittest.TestCase):
    def test_size_boundaries_before_reader(self):
        for size in (limits.MAX_PDF_BYTES - 1, limits.MAX_PDF_BYTES, limits.MAX_PDF_BYTES + 1):
            data = Mock()
            data.__len__ = Mock(return_value=size)
            with self.subTest(size=size), patch("pdf_engine.validator.BytesIO") as buffer, patch("pdf_engine.validator.PdfReader") as reader:
                reader.return_value.trailer = {"/Root": {"/Pages": {"/Count": 1}}}
                reader.return_value.is_encrypted = False
                reader.return_value.pages = [object()]
                if size > limits.MAX_PDF_BYTES:
                    with self.assertRaises(PdfEngineError):
                        validate_pdf(data)
                    buffer.assert_not_called()
                    reader.assert_not_called()
                else:
                    validate_pdf(data)
                    reader.assert_called_once()

    def test_page_boundaries(self):
        for count in (299, 300, 301):
            with self.subTest(count=count):
                source = make_pdf([72] * count)
                if count > 300:
                    with self.assertRaises(PdfEngineError):
                        validate_pdf(source)
                else:
                    self.assertEqual(len(validate_pdf(source).pages), count)

    def test_file_count_boundaries(self):
        source = make_pdf()
        for count in (9, 10):
            with self.subTest(count=count):
                validate_pdf(merge_pdfs([source] * count))
        with patch("pdf_engine.merger.validate_pdf") as validate:
            with self.assertRaises(PdfEngineError):
                merge_pdfs(source for _ in range(11))
            validate.assert_not_called()

    def test_total_boundaries_before_writer(self):
        for counts in ((300, 300, 300, 99), (300, 300, 300, 100), (300, 300, 300, 101)):
            with self.subTest(counts=counts), patch("pdf_engine.merger.PdfWriter") as writer:
                sources = [make_pdf([72] * count) for count in counts]
                if sum(counts) > 1000:
                    with self.assertRaises(PdfEngineError):
                        merge_pdfs(sources)
                    writer.assert_not_called()
                else:
                    merge_pdfs(sources)
                    self.assertEqual(writer.return_value.add_page.call_count, sum(counts))

    def test_every_processor_enforces_size_and_pages(self):
        processors = (
            lambda data: split_pdf(data), lambda data: merge_pdfs([data]),
            lambda data: extract_pages(data, "1"), lambda data: reorder_pages(data, "1"),
            lambda data: rotate_pdf(data, 90), lambda data: add_watermark(data, "Test"),
            lambda data: compress_pdf(data, "medium"),
        )
        for process in processors:
            with patch.object(limits, "MAX_PDF_BYTES", 1):
                with self.assertRaises(PdfEngineError):
                    process(make_pdf())
            with self.assertRaises(PdfEngineError):
                process(make_pdf([72] * 301))

    def test_repeated_selection_is_bounded_before_expansion(self):
        from pdf_engine.page_parser import parse_page_selection
        for count in (999, 1000):
            self.assertEqual(len(parse_page_selection(",".join(["1"] * count), 1)), count)
        with patch("pdf_engine.page_parser.range", create=True) as expand:
            with self.assertRaises(PdfEngineError):
                parse_page_selection(",".join(["1"] * 1001), 1)
            expand.assert_not_called()

    def test_merge_loaders_are_not_called_for_excess_file_count(self):
        loader = Mock()
        with self.assertRaises(PdfEngineError):
            merge_pdfs([loader] * 11)
        loader.assert_not_called()

    def test_real_merge_at_total_limit_preserves_all_pages(self):
        inputs = [make_pdf([72] * count) for count in (300, 300, 300, 100)]
        result = merge_pdfs(inputs)
        self.assertEqual(len(PdfReader(BytesIO(result)).pages), 1000)

    def test_oversized_compressor_output_is_not_read_and_is_cleaned(self):
        import subprocess
        from pathlib import Path
        paths = []
        def run(command, **kwargs):
            output = Path(command[-2].split("=", 1)[1])
            output.write_bytes(b"partial")
            paths.append(output.parent)
            return subprocess.CompletedProcess(command, 0, "", "")
        stat = Mock(st_size=limits.MAX_PDF_BYTES + 1)
        with patch("pdf_engine.compressor.subprocess.run", side_effect=run), patch("pdf_engine.compressor.Path.stat", return_value=stat), patch("pdf_engine.compressor.Path.is_file", return_value=True), patch("pdf_engine.compressor.Path.read_bytes") as read:
            with self.assertRaises(PdfEngineError):
                compress_pdf(make_pdf(), "medium")
            read.assert_not_called()
        self.assertTrue(all(not path.exists() for path in paths))

    def test_declared_page_limit_prevents_flattening(self):
        reader = Mock()
        reader.is_encrypted = False
        reader.trailer = {"/Root": {"/Pages": {"/Count": 301}}}
        reader.pages = Mock()
        with patch("pdf_engine.validator.PdfReader", return_value=reader):
            with self.assertRaises(PdfEngineError):
                validate_pdf(b"controlled input")

    def test_low_declared_count_does_not_bypass_actual_page_limit(self):
        reader = Mock()
        reader.is_encrypted = False
        reader.trailer = {"/Root": {"/Pages": {"/Count": 1}}}
        reader.pages = [object()] * 301
        with patch("pdf_engine.validator.PdfReader", return_value=reader):
            with self.assertRaises(PdfEngineError):
                validate_pdf(b"controlled input")
