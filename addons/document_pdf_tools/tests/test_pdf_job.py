import base64
from io import BytesIO
from pathlib import Path

from lxml import etree
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

    def test_failed_job_can_be_corrected_and_processed_again(self):
        job = self._make_job("Retry extraction")
        job.write({"operation": "extract", "page_selection": "3"})
        job.action_process()
        self.assertEqual(job.state, "failed")
        self.assertEqual(job.error_message, "Page 3 does not exist.")
        input_ids = job.input_attachment_ids.ids

        job.action_reset_to_draft()

        self.assertEqual(job.state, "draft")
        self.assertFalse(job.error_message)
        self.assertEqual(job.input_attachment_ids.ids, input_ids)
        self.assertEqual(job.page_selection, "3")
        job.page_selection = "2"
        job.action_process()
        self.assertEqual(job.state, "done")
        self.assertFalse(job.error_message)
        self.assertEqual(len(job.output_attachment_ids), 1)
        reader = PdfReader(BytesIO(base64.b64decode(job.output_attachment_ids.datas)))
        self.assertEqual(len(reader.pages), 1)
        self.assertEqual(float(reader.pages[0].mediabox.width), 144)

    def test_reset_rejects_non_failed_jobs_without_partial_changes(self):
        for state in ("draft", "processing", "done"):
            with self.subTest(state=state):
                failed = self._make_job("Failed job")
                failed.write({"state": "failed", "error_message": "Original error"})
                other = self._make_job("Non-failed job")
                other.write({"state": state})
                with self.assertRaises(UserError):
                    (failed | other).action_reset_to_draft()
                self.assertEqual(failed.state, "failed")
                self.assertEqual(failed.error_message, "Original error")
                self.assertEqual(other.state, state)

    def test_retry_failure_records_new_error(self):
        job = self._make_job("Retry fails")
        job.write({"operation": "extract", "page_selection": "3"})
        job.action_process()
        self.assertEqual(job.state, "failed")
        self.assertEqual(job.error_message, "Page 3 does not exist.")

        job.action_reset_to_draft()
        job.page_selection = "4"
        job.action_process()

        self.assertEqual(job.state, "failed")
        self.assertEqual(job.error_message, "Page 4 does not exist.")
        self.assertFalse(job.output_attachment_ids)

    def test_multiple_failed_jobs_can_be_reset(self):
        jobs = self._make_job("First failed job") | self._make_job("Second failed job")
        jobs.write({"state": "failed", "error_message": "Previous error"})
        jobs.action_reset_to_draft()
        self.assertEqual(jobs.mapped("state"), ["draft", "draft"])
        self.assertTrue(all(not job.error_message for job in jobs))

    def test_form_exposes_reset_only_for_failed_jobs(self):
        # Load the updated source view transactionally, without upgrading the database.
        path = Path(__file__).resolve().parents[1] / "views" / "pdf_job_views.xml"
        document = etree.parse(str(path))
        form = document.xpath("//record[@id='view_pdf_job_form']/field[@name='arch']/form")[0]
        view = self.env.ref("document_pdf_tools.view_pdf_job_form")
        view.write({"arch_db": etree.tostring(form, encoding="unicode")})
        arch = self.env["pdf.job"].get_view(view_id=view.id, view_type="form")["arch"]
        form = etree.fromstring(arch.encode())
        reset = form.xpath("//button[@name='action_reset_to_draft']")
        self.assertEqual(len(reset), 1)
        self.assertEqual(reset[0].get("invisible"), "state != 'failed'")
        process = form.xpath("//button[@name='action_process']")[0]
        self.assertEqual(process.get("invisible"), "state != 'draft'")
