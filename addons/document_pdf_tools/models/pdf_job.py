import base64
import logging

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from pdf_engine.extractor import extract_pages
from pdf_engine import limits
from pdf_engine.exceptions import PdfEngineError, PageSelectionError

from pdf_engine.compressor import compress_pdf
from pdf_engine.merger import merge_pdfs
from pdf_engine.splitter import split_pdf
from pdf_engine.rotator import rotate_pdf
from pdf_engine.reorder import reorder_pages
from pdf_engine.watermark import add_watermark

_logger = logging.getLogger(__name__)


class PdfJob(models.Model):
    _name = "pdf.job"
    _description = "PDF Processing Job"
    _order = "create_date desc"

    name = fields.Char(required=True)

    # The existing audit field is the owner, including for pre-existing jobs.
    @api.model_create_multi
    def create(self, vals_list):
        if not self.env.is_system():
            for vals in vals_list:
                if vals.get("create_uid", self.env.uid) != self.env.uid:
                    raise AccessError("You cannot assign a PDF job to another user.")
                vals["create_uid"] = self.env.uid
        return super().create(vals_list)

    def write(self, vals):
        if "create_uid" in vals and not self.env.is_system():
            raise AccessError("You cannot change the owner of a PDF job.")
        return super().write(vals)

    operation = fields.Selection(
        [
            ("merge", "Merge"),
            ("split", "Split"),
            ("rotate", "Rotate"),
            ("reorder", "Reorder"),
            ("extract", "Extract Pages"),
            ("watermark", "Watermark"),
            ("compress", "Compress"),
        ],
        required=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("processing", "Processing"),
            ("done", "Done"),
            ("failed", "Failed"),
        ],
        default="draft",
        required=True,
        readonly=True,
    )

    input_attachment_ids = fields.Many2many(
        "ir.attachment",
        "pdf_job_input_attachment_rel",
        "job_id",
        "attachment_id",
        string="Input PDFs",
    )

    output_attachment_ids = fields.Many2many(
        "ir.attachment",
        "pdf_job_output_attachment_rel",
        "job_id",
        "attachment_id",
        string="Output PDFs",
        readonly=True,
    )

    error_message = fields.Text(readonly=True)

    rotation_angle = fields.Selection(
        [
            ("90", "90°"),
            ("180", "180°"),
            ("270", "270°"),
        ],
        string="Rotation",
        default="90",
        required=True,
    )

    page_selection = fields.Char(
        string="Pages",
        help="Example: 1,3,5-8,12",
    )

    watermark_text = fields.Char(
        string="Watermark Text",
    )

    compression_level = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
        string="Compression Level",
        default="medium",
        required=True,
    )

    def action_reset_to_draft(self):
        if any(job.state != "failed" for job in self):
            raise UserError("Only failed jobs can be reset to draft.")
        self.write({"state": "draft", "error_message": False})

    def action_process(self):
        # Authorize the whole recordset before entering error-handling savepoints.
        self.check_access("write")
        if any(job.state != "draft" for job in self):
            raise UserError("Only draft jobs can be processed. Reset failed jobs to draft before retrying.")
        operation_methods = {
            "merge": "_process_merge",
            "split": "_process_split",
            "rotate": "_process_rotate",
            "extract": "_process_extract",
            "reorder": "_process_reorder",
            "watermark": "_process_watermark",
            "compress": "_process_compress",
        }

        for job in self:
            try:
                with self.env.cr.savepoint():
                    job.write({
                        "state": "processing",
                        "error_message": False,
                    })
                    method_name = operation_methods.get(job.operation)
                    if not method_name:
                        raise UserError(f"No processor available for operation: {job.operation}")
                    getattr(job, method_name)()
                    job.state = "done"
            except Exception as error:
                if isinstance(error, (UserError, PdfEngineError, PageSelectionError)):
                    message = str(error)
                else:
                    message = "PDF processing failed. Please contact your administrator."
                    _logger.exception("PDF job %s failed", job.id)
                job.write({
                    "state": "failed",
                    "error_message": message,
                })

    def _create_output_attachment(self, name, data):
        return self.env["ir.attachment"].create({
            "name": name,
            "type": "binary",
            "datas": base64.b64encode(data),
            "mimetype": "application/pdf",
            "res_model": "pdf.job",
            "res_id": self.id,
        })

    def _load_pdf_attachment(self, attachment):
        # Metadata rejects oversized inputs before accessing their binary data.
        limits.check_pdf_size(attachment.file_size)
        # Avoid base64 overhead and binary-field prefetch across all attachments.
        attachment = attachment.with_context(bin_size=False, prefetch_fields=False)
        try:
            source = attachment.raw or b""
            limits.check_pdf_size(len(source))
            return source
        finally:
            # Odoo's environment cache must not retain every input in a merge.
            attachment.invalidate_recordset(["raw", "datas"], flush=False)

    def _check_input_resources(self):
        limits.check_pdf_count(len(self.input_attachment_ids))
        for attachment in self.input_attachment_ids:
            limits.check_pdf_size(attachment.file_size)

    def _process_merge(self):
        self._check_input_resources()
        if len(self.input_attachment_ids) < 2:
            raise UserError("Merge requires at least two PDFs.")
        pdf_files = [
            (lambda attachment=att: self._load_pdf_attachment(attachment))
            for att in self.input_attachment_ids
        ]
        merged_pdf = merge_pdfs(pdf_files)
        attachment = self._create_output_attachment(
            f"{self.name}_merged.pdf",
            merged_pdf,
        )

        self.output_attachment_ids = [(6, 0, [attachment.id])]

    def _process_split(self):
        self._check_input_resources()
        if len(self.input_attachment_ids) != 1:
            raise UserError("Split requires exactly one PDF.")

        source = self._load_pdf_attachment(self.input_attachment_ids[0])
        pages = split_pdf(source)
        attachment_ids = []

        for page in pages:
            attachment = self._create_output_attachment(
                f"{self.name}_page_{page['page']}.pdf",
                page["data"],
            )
            attachment_ids.append(attachment.id)

        self.output_attachment_ids = [(6, 0, attachment_ids)]

    def _process_rotate(self):
        self._check_input_resources()
        if len(self.input_attachment_ids) != 1:
            raise UserError("Rotate requires exactly one PDF.")

        source = self._load_pdf_attachment(self.input_attachment_ids[0])
        rotated_pdf = rotate_pdf(
            source,
            int(self.rotation_angle),
        )
        attachment = self._create_output_attachment(
            f"{self.name}_rotated.pdf",
            rotated_pdf,
        )

        self.output_attachment_ids = [(6, 0, [attachment.id])]

    def _process_extract(self):
        self._check_input_resources()
        if len(self.input_attachment_ids) != 1:
            raise UserError("Extract requires exactly one PDF.")

        if not self.page_selection:
            raise UserError("Enter the pages to extract.")

        source = self._load_pdf_attachment(self.input_attachment_ids[0])
        extracted_pdf = extract_pages(
            source,
            self.page_selection,
        )
        attachment = self._create_output_attachment(
            f"{self.name}_extracted.pdf",
            extracted_pdf,
        )

        self.output_attachment_ids = [(6, 0, [attachment.id])]

    def _process_reorder(self):
        self._check_input_resources()
        if len(self.input_attachment_ids) != 1:
            raise UserError("Reorder requires exactly one PDF.")

        if not self.page_selection:
            raise UserError("Enter the pages to reorder.")

        source = self._load_pdf_attachment(self.input_attachment_ids[0])
        extracted_pdf = reorder_pages(
            source,
            self.page_selection,
        )
        attachment = self._create_output_attachment(
            f"{self.name}_reordered.pdf",
            extracted_pdf,
        )

        self.output_attachment_ids = [(6, 0, [attachment.id])]

    def _process_watermark(self):
        self._check_input_resources()
        if len(self.input_attachment_ids) != 1:
            raise UserError("Watermark requires exactly one PDF.")

        if not self.watermark_text:
            raise UserError("Enter the watermark text.")

        source = self._load_pdf_attachment(self.input_attachment_ids[0])
        watermarked_pdf = add_watermark(
            source,
            self.watermark_text,
        )
        attachment = self._create_output_attachment(
            f"{self.name}_watermarked.pdf",
            watermarked_pdf,
        )

        self.output_attachment_ids = [(6, 0, [attachment.id])]

    def _process_compress(self):
        self._check_input_resources()
        if len(self.input_attachment_ids) != 1:
            raise UserError("Compress requires exactly one PDF.")

        source = self._load_pdf_attachment(self.input_attachment_ids[0])
        compressed_pdf = compress_pdf(
            source,
            self.compression_level,
        )
        attachment = self._create_output_attachment(
            f"{self.name}_compressed.pdf",
            compressed_pdf,
        )

        self.output_attachment_ids = [(6, 0, [attachment.id])]
