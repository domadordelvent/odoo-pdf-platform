from unittest.mock import patch

from odoo.tests.common import TransactionCase
from pdf_engine import limits
from . import test_pdf_job


class TestResourceLimits(TransactionCase):
    _make_job = test_pdf_job.TestPdfJobTransactions._make_job

    def test_all_operations_reject_oversize_before_decode(self):
        for operation in ("split", "merge", "extract", "reorder", "rotate", "watermark", "compress"):
            with self.subTest(operation=operation):
                job = self._make_job("Oversized input")
                job.operation = operation
                with patch.object(limits, "MAX_PDF_BYTES", 1), patch.object(type(job), "_load_pdf_attachment") as load:
                    job.action_process()
                    load.assert_not_called()
                self.assertEqual(job.state, "failed")
                self.assertIn("at most", job.error_message)
                self.assertFalse(job.output_attachment_ids)

    def test_count_is_checked_before_loading(self):
        job = self._make_job("Too many inputs")
        job.operation = "merge"
        attachments = job.input_attachment_ids
        for _ in range(10):
            attachments |= job.input_attachment_ids.copy()
        job.input_attachment_ids = attachments
        with patch.object(type(job), "_load_pdf_attachment") as load:
            job.action_process()
            load.assert_not_called()
        self.assertEqual(job.state, "failed")
        self.assertIn("10 PDFs", job.error_message)

    def test_internal_errors_do_not_reveal_details(self):
        job = self._make_job("Internal failure")
        with patch.object(type(job), "_process_split", side_effect=ValueError("secret /private/path")):
            job.action_process()
        self.assertEqual(job.state, "failed")
        self.assertNotIn("secret", job.error_message)
        self.assertNotIn("/private", job.error_message)

    def test_page_and_total_limits_apply_from_odoo(self):
        from io import BytesIO
        import base64
        from pypdf import PdfWriter
        for counts in ((301,), (300, 300, 300, 101)):
            job = self._make_job("Page limits")
            job.operation = "split" if len(counts) == 1 else "merge"
            attachments = self.env["ir.attachment"]
            for count in counts:
                writer = PdfWriter()
                for _ in range(count):
                    writer.add_blank_page(width=72, height=300)
                output = BytesIO()
                writer.write(output)
                attachments |= self.env["ir.attachment"].create({
                    "name": "input.pdf", "datas": base64.b64encode(output.getvalue()),
                    "res_model": "pdf.job", "res_id": job.id,
                })
            job.input_attachment_ids = attachments
            with patch.object(type(job), "_create_output_attachment") as create:
                job.action_process()
                create.assert_not_called()
            self.assertEqual(job.state, "failed")
            self.assertIn("at most", job.error_message)

    def test_valid_merge_uses_lazy_loaders_and_preserves_output(self):
        from io import BytesIO
        import base64
        from pypdf import PdfReader
        job = self._make_job("Valid merge")
        job.operation = "merge"
        job.input_attachment_ids |= job.input_attachment_ids.copy()
        job.action_process()
        self.assertEqual(job.state, "done")
        self.assertEqual(len(job.output_attachment_ids), 1)
        reader = PdfReader(BytesIO(base64.b64decode(job.output_attachment_ids.datas)))
        self.assertEqual(len(reader.pages), 4)

    def test_binary_size_context_does_not_replace_input_bytes(self):
        job = self._make_job("Binary context")
        source = job.with_context(bin_size=True)._load_pdf_attachment(job.input_attachment_ids)
        self.assertIsInstance(source, bytes)
        self.assertTrue(source.startswith(b"%PDF-"))
