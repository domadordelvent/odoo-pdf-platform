from odoo import api, models
from odoo.osv import expression


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None):
        if not self.env.su:
            jobs = self.env["pdf.job"]
            allowed_jobs = jobs._search([]) if jobs.has_access("read") else []
            # Odoo's attachment search accepts public files without checking
            # their linked records. Keep job attachments subject to job rules.
            domain = expression.AND([domain, [
                "|", ("res_model", "!=", "pdf.job"),
                "|", ("res_id", "in", [False, 0]),
                ("res_id", "in", allowed_jobs),
            ]])
        return super()._search(domain, offset=offset, limit=limit, order=order)

    def _check_pdf_job_access(self, mode):
        # Inspect the linkage only; never return attachment data under sudo.
        linked = self.sudo().filtered(
            lambda attachment: attachment.res_model == "pdf.job" and attachment.res_id
        )
        if linked:
            jobs = self.env["pdf.job"].browse(linked.mapped("res_id"))
            jobs.check_access("write" if mode in ("create", "unlink") else mode)

    def check(self, mode, values=None):
        # Odoo normally skips the linked record check for public attachments.
        # PDF job privacy must also apply to existing public attachments.
        self._check_pdf_job_access(mode)
        return super().check(mode, values)

    def validate_access(self, access_token):
        self.ensure_one()
        attachment = self.sudo()
        if attachment.res_model == "pdf.job" and attachment.res_id:
            # /web/content normally permits public or token-based sudo access.
            # PDFs belonging to jobs always require the job's record access.
            self.check("read")
            return self
        return super().validate_access(access_token)
