import base64

from odoo import fields, models
from odoo.exceptions import UserError

from pdf_engine.extractor import extract_pages

from pdf_engine.merger import merge_pdfs
from pdf_engine.splitter import split_pdf
from pdf_engine.rotator import rotate_pdf
from pdf_engine.reorder import reorder_pages
from pdf_engine.watermark import add_watermark

class PdfJob(models.Model):
    _name = "pdf.job"
    _description = "PDF Processing Job"
    _order = "create_date desc"

    name = fields.Char(required=True)

    operation = fields.Selection(
        [
            ("merge", "Merge"),
            ("split", "Split"),
            ("rotate", "Rotate"),
            ("reorder", "Reorder"),
            ("extract", "Extract Pages"),
            ("watermark", "Watermark"),
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
    )

    page_selection = fields.Char(
        string="Pages",
        help="Example: 1,3,5-8,12",
    )

    watermark_text = fields.Char(
        string="Watermark Text",
    )

#Barreja els dos documents, canvia l'estat a processing, crea el nou document
#i canvia l'estat a done
    def action_process(self):
        for job in self:
            if job.operation == "merge":
                pdf_files = [
                    base64.b64decode(att.datas)
                    for att in job.input_attachment_ids
                ]

                merged_pdf = merge_pdfs(pdf_files)

                attachment = self.env["ir.attachment"].create({
                    "name": f"{job.name}_merged.pdf",
                    "type": "binary",
                    "datas": base64.b64encode(merged_pdf),
                    "mimetype": "application/pdf",
                    "res_model": "pdf.job",
                    "res_id": job.id,
                })

                job.output_attachment_ids = [(6, 0, [attachment.id])]

            elif job.operation == "split":
                if len(job.input_attachment_ids) != 1:
                    raise UserError("Split requires exactly one PDF.")

                source = base64.b64decode(job.input_attachment_ids[0].datas)

                pages = split_pdf(source)

                attachment_ids = []

                for page in pages:
                    attachment = self.env["ir.attachment"].create({
                        "name": f"{job.name}_page_{page['page']}.pdf",
                        "type": "binary",
                        "datas": base64.b64encode(page["data"]),
                        "mimetype": "application/pdf",
                        "res_model": "pdf.job",
                        "res_id": job.id,
                    })

                    attachment_ids.append(attachment.id)

                job.output_attachment_ids = [(6, 0, attachment_ids)]
            elif job.operation == "rotate":
                if len(job.input_attachment_ids) != 1:
                    raise UserError("Rotate requires exactly one PDF.")

                source = base64.b64decode(job.input_attachment_ids[0].datas)

                rotated_pdf = rotate_pdf(
                    source,
                    int(job.rotation_angle),
                )

                attachment = self.env["ir.attachment"].create({
                    "name": f"{job.name}_rotated.pdf",
                    "type": "binary",
                    "datas": base64.b64encode(rotated_pdf),
                    "mimetype": "application/pdf",
                    "res_model": "pdf.job",
                    "res_id": job.id,
                })

                job.output_attachment_ids = [(6, 0, [attachment.id])]
            elif job.operation == "extract":
                if len(job.input_attachment_ids) != 1:
                    raise UserError("Extract requires exactly one PDF.")

                if not job.page_selection:
                    raise UserError("Enter the pages to extract.")

                source = base64.b64decode(job.input_attachment_ids[0].datas)

                extracted_pdf = extract_pages(
                    source,
                    job.page_selection,
                )

                attachment = self.env["ir.attachment"].create({
                    "name": f"{job.name}_extracted.pdf",
                    "type": "binary",
                    "datas": base64.b64encode(extracted_pdf),
                    "mimetype": "application/pdf",
                    "res_model": "pdf.job",
                    "res_id": job.id,
                })

                job.output_attachment_ids = [(6, 0, [attachment.id])]

            elif job.operation == "reorder":
                if len(job.input_attachment_ids) != 1:
                    raise UserError("Reorder requires exactly one PDF.")

                if not job.page_selection:
                    raise UserError("Enter the pages to reorder.")

                source = base64.b64decode(job.input_attachment_ids[0].datas)

                extracted_pdf = reorder_pages(
                    source,
                    job.page_selection,
                )

                attachment = self.env["ir.attachment"].create({
                    "name": f"{job.name}_extracted.pdf",
                    "type": "binary",
                    "datas": base64.b64encode(extracted_pdf),
                    "mimetype": "application/pdf",
                    "res_model": "pdf.job",
                    "res_id": job.id,
                })

                job.output_attachment_ids = [(6, 0, [attachment.id])]
            elif job.operation == "watermark":
                if len(job.input_attachment_ids) != 1:
                    raise UserError("Watermark requires exactly one PDF.")

                if not job.watermark_text:
                    raise UserError("Enter the watermark text.")

                source = base64.b64decode(
                    job.input_attachment_ids[0].datas
                )

                watermarked_pdf = add_watermark(
                    source,
                    job.watermark_text,
                )

                attachment = self.env["ir.attachment"].create({
                    "name": f"{job.name}_watermarked.pdf",
                    "type": "binary",
                    "datas": base64.b64encode(watermarked_pdf),
                    "mimetype": "application/pdf",
                    "res_model": "pdf.job",
                    "res_id": job.id,
                })

                job.output_attachment_ids = [(6, 0, [attachment.id])]