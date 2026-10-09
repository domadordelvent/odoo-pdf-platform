import base64
from io import BytesIO
from unittest.mock import patch

from pypdf import PdfWriter

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tests.common import new_test_user


class PdfSecurityFixtures:
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user_a = new_test_user(cls.env, login="pdf_security_a", groups="base.group_user")
        cls.user_b = new_test_user(cls.env, login="pdf_security_b", groups="base.group_user")
        cls.admin = new_test_user(
            cls.env, login="pdf_security_admin", groups="base.group_system"
        )
        cls.job = cls.env["pdf.job"].with_user(cls.user_a).create({
            "name": "Private PDF", "operation": "split",
        })
        writer = PdfWriter()
        writer.add_blank_page(width=72, height=144)
        output = BytesIO()
        writer.write(output)
        cls.pdf_bytes = output.getvalue()
        cls.input_pdf = cls.env["ir.attachment"].with_user(cls.user_a).create({
            "name": "private.pdf",
            "datas": base64.b64encode(cls.pdf_bytes),
            "mimetype": "application/pdf",
            "res_model": "pdf.job", "res_id": cls.job.id,
        })
        cls.job.input_attachment_ids = [(6, 0, cls.input_pdf.ids)]
        cls.job.action_process()
        cls.attachments = cls.input_pdf | cls.job.output_attachment_ids


class TestPdfJobSecurity(PdfSecurityFixtures, TransactionCase):
    def test_owner_can_read_write_process_and_delete(self):
        self.assertEqual(self.job.create_uid, self.user_a)
        self.assertEqual(self.job.read(["name"])[0]["name"], "Private PDF")
        self.job.write({"name": "Updated private PDF"})
        self.job.action_process()
        self.assertEqual(self.job.state, "done")
        for attachment in self.attachments:
            self.assertTrue(attachment.with_user(self.user_a).read(["datas"])[0]["datas"])
        self.job.unlink()

    def test_other_user_cannot_find_or_access_job(self):
        jobs = self.env["pdf.job"].with_user(self.user_b)
        self.assertFalse(jobs.search([("id", "=", self.job.id)]))
        target = self.job.with_user(self.user_b)
        for operation in (
            lambda: target.read(["name"]),
            lambda: target.write({"name": "Stolen"}),
            target.unlink,
            target.action_process,
        ):
            with self.assertRaises(AccessError):
                operation()

    def test_process_authorizes_entire_batch_before_processing(self):
        own_job = self.env["pdf.job"].with_user(self.user_b).create({
            "name": "B's job", "operation": "split",
        })
        with patch.object(type(self.job), "_process_split") as process:
            with self.assertRaises(AccessError):
                (own_job | self.job.with_user(self.user_b)).action_process()
            process.assert_not_called()

    def test_group_rule_cannot_widen_owner_access(self):
        self.env["ir.rule"].create({
            "name": "Permissive group rule",
            "model_id": self.env["ir.model"]._get_id("pdf.job"),
            "groups": [(6, 0, self.env.ref("base.group_user").ids)],
            "domain_force": "[(1, '=', 1)]",
        })
        self.assertFalse(self.env["pdf.job"].with_user(self.user_b).search([
            ("id", "=", self.job.id),
        ]))
        with self.assertRaises(AccessError):
            self.job.with_user(self.user_b).read(["name"])

    def test_owner_can_read_attachment_uploaded_by_administrator(self):
        attachment = self.env["ir.attachment"].with_user(self.admin).create({
            "name": "Admin upload.pdf", "datas": base64.b64encode(self.pdf_bytes),
            "res_model": "pdf.job", "res_id": self.job.id,
        })
        self.assertTrue(attachment.with_user(self.user_a).read(["datas"])[0]["datas"])
        with self.assertRaises(AccessError):
            attachment.with_user(self.user_b).read(["datas"])

    def test_owner_cannot_be_forged_or_changed(self):
        jobs = self.env["pdf.job"].with_user(self.user_b)
        with self.assertRaises(AccessError):
            jobs.create({"name": "Forged", "operation": "split", "create_uid": self.user_a.id})
        own = jobs.with_context(default_create_uid=self.user_a.id).create({
            "name": "Context forgery", "operation": "split",
        })
        self.assertEqual(own.create_uid, self.user_b)
        with self.assertRaises(AccessError):
            self.job.write({"create_uid": self.user_b.id})
        with self.assertRaises(AccessError):
            own.write({"create_uid": self.user_a.id})
        with self.assertRaises(AccessError):
            self.job.with_user(self.user_b).write({"create_uid": self.user_b.id})

    def test_other_user_cannot_read_modify_delete_or_rebind_attachments(self):
        for attachment in self.attachments.with_user(self.user_b):
            for operation in (
                lambda: attachment.read(["datas"]),
                lambda: attachment.write({"name": "Stolen"}),
                lambda: attachment.write({"res_model": False, "res_id": 0}),
                attachment.unlink,
            ):
                with self.assertRaises(AccessError):
                    operation()
        with self.assertRaises(AccessError):
            self.env["ir.attachment"].with_user(self.user_b).create({
                "name": "Injected", "res_model": "pdf.job", "res_id": self.job.id,
            })

    def test_public_and_token_attachments_still_require_job_access(self):
        self.attachments.with_user(self.user_a).write({"public": True, "access_token": "pdf-test-token"})
        self.assertFalse(self.env["ir.attachment"].with_user(self.user_b).search([
            ("id", "in", self.attachments.ids),
        ]))
        for attachment in self.attachments.with_user(self.user_b):
            with self.assertRaises(AccessError):
                attachment.read(["datas"])
            with self.assertRaises(AccessError):
                attachment.validate_access("pdf-test-token")

    def test_administrator_has_access_without_sudo(self):
        job = self.job.with_user(self.admin)
        self.assertFalse(job.env.su)
        self.assertEqual(self.env["pdf.job"].with_user(self.admin).search([("id", "=", job.id)]), job)
        job.read(["name"])
        job.write({"name": "Admin updated"})
        job.action_process()
        self.assertEqual(job.state, "done")
        for attachment in self.attachments.with_user(self.admin):
            self.assertTrue(attachment.read(["datas"])[0]["datas"])
        job.unlink()

    def test_unrelated_attachments_keep_standard_behavior(self):
        attachment = self.env["ir.attachment"].create({
            "name": "Public unrelated", "datas": base64.b64encode(b"unrelated"), "public": True,
        })
        self.assertTrue(attachment.with_user(self.user_b).validate_access(None).env.su)


@tagged("post_install", "-at_install")
class TestPdfAttachmentDownloads(PdfSecurityFixtures, HttpCase):
    def test_downloads_require_owner_or_administrator(self):
        for public in (False, True):
            self.attachments.write({"public": public, "access_token": "pdf-test-token"})
            for user in (self.user_a, self.user_b, self.admin):
                self.authenticate(user.login, user.login)
                for attachment in self.attachments:
                    for suffix in ("", "&access_token=pdf-test-token"):
                        response = self.url_open(f"/web/content/{attachment.id}?download=true{suffix}")
                        if user == self.user_b:
                            self.assertIn(response.status_code, (403, 404))
                            self.assertNotIn(b"%PDF-", response.content)
                        else:
                            self.assertEqual(response.status_code, 200)
                            self.assertTrue(response.content.startswith(b"%PDF-"))
            self.authenticate(None, None)
            for attachment in self.attachments:
                response = self.url_open(f"/web/content/{attachment.id}?download=true&access_token=pdf-test-token")
                self.assertIn(response.status_code, (403, 404))
