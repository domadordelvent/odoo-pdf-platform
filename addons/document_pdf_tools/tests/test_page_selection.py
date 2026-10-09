from unittest.mock import patch

from odoo.tests.common import TransactionCase

from . import test_pdf_job


class TestPageSelection(TransactionCase):
    _make_job = test_pdf_job.TestPdfJobTransactions._make_job

    def test_invalid_selections_fail_without_creating_outputs(self):
        for operation in ("extract", "reorder"):
            for selection in ("1-1000000000", "1-3", "2-1", "1,,2"):
                with self.subTest(operation=operation, selection=selection):
                    job = self._make_job("Invalid selection")
                    job.write({"operation": operation, "page_selection": selection})
                    with patch.object(type(job), "_create_output_attachment") as create:
                        job.action_process()
                        create.assert_not_called()
                    self.assertEqual(job.state, "failed")
                    self.assertTrue(job.error_message)
                    self.assertFalse(job.output_attachment_ids)
