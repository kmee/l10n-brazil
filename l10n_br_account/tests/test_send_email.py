# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSendEmail(TransactionCase):
    def test_send_email_without_fiscal_notification(self):
        document_model = self.env["l10n_br_fiscal.document"]
        if hasattr(document_model, "action_send_email"):
            self.skipTest("l10n_br_fiscal_notification is installed")
        move = self.env["account.move"].create({"move_type": "out_invoice"})
        with self.assertRaises(UserError):
            move.action_send_email()
