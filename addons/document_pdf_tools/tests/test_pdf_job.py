import base64
from io import BytesIO
from unittest.mock import patch

from pypdf import PdfReader, PdfWriter

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase
from odoo.tools import mute_logger


class TestPdfJobTransactions(TransactionCase):
    def _make_job(self, name):
        job = self.env["pdf.job"].create({"name": name, "operation": "split"})
        writer = PdfWriter()
        for width in (72, 144):
            writer.add_blank_page(width=width, height=300)
        source = BytesIO()
        writer.write(source)
        attachment = self.env["ir.attachment"].create({
            "name": "input.pdf",
            "datas": base64.b64encode(source.getvalue()),
            "res_model": "pdf.job",
            "res_id": job.id,
        })
        job.input_attachment_ids = [(6, 0, attachment.ids)]
        return job

    def _process_with_failure(self, jobs, failed_job, sql_error=False):
        model = type(failed_job)
        original = model._create_output_attachment
        partial_ids = []

        def create_output(job, name, data):
            if job.id == failed_job.id and partial_ids:
                if sql_error:
                    job.env.cr.execute("SELECT 1 / 0")
                raise UserError("Attachment processing failed")
            attachment = original(job, name, data)
            if job.id == failed_job.id:
                partial_ids.append(attachment.id)
                # Include a relation and an ordinary field in the rollback.
                job.write({
                    "name": "Partial change",
                    "output_attachment_ids": [(6, 0, attachment.ids)],
                })
                job.env.flush_all()
            return attachment

        with patch.object(model, "_create_output_attachment", create_output):
            with mute_logger("odoo.sql_db"):
                jobs.action_process()
        self.env.flush_all()
        self.env.invalidate_all()
        self.assertEqual(len(partial_ids), 1)
        self.assertFalse(self.env["ir.attachment"].browse(partial_ids).exists())
        self.assertFalse(failed_job.output_attachment_ids)

    def test_partial_attachments_and_job_changes_roll_back(self):
        job = self._make_job("Python failure")
        input_ids = job.input_attachment_ids.ids

        self._process_with_failure(job, job)

        self.assertEqual(job.name, "Python failure")
        self.assertEqual(job.input_attachment_ids.ids, input_ids)
        self.assertEqual(job.state, "failed")
        self.assertEqual(job.error_message, "Attachment processing failed")

    def test_sql_failure_records_error_after_rollback(self):
        job = self._make_job("SQL failure")

        self._process_with_failure(job, job, sql_error=True)

        self.assertEqual(job.name, "SQL failure")
        self.assertEqual(job.state, "failed")
        self.assertIn("division by zero", job.error_message)
        self.env.cr.execute("SELECT 1")
        self.assertEqual(self.env.cr.fetchone(), (1,))

    def test_subsequent_job_succeeds_after_sql_failure(self):
        failed_job = self._make_job("First job")
        successful_job = self._make_job("Second job")
        successful_job.error_message = "Previous error"

        self._process_with_failure(
            failed_job | successful_job, failed_job, sql_error=True
        )

        self.assertEqual(failed_job.state, "failed")
        self.assertIn("division by zero", failed_job.error_message)
        self.assertEqual(successful_job.state, "done")
        self.assertFalse(successful_job.error_message)
        outputs = successful_job.output_attachment_ids.sorted("name")
        self.assertEqual(len(outputs), 2)
        widths = []
        for attachment in outputs:
            reader = PdfReader(BytesIO(base64.b64decode(attachment.datas)))
            self.assertEqual(len(reader.pages), 1)
            widths.append(float(reader.pages[0].mediabox.width))
            self.assertEqual(attachment.res_model, "pdf.job")
            self.assertEqual(attachment.res_id, successful_job.id)
        self.assertEqual(widths, [72, 144])
