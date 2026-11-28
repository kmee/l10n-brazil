# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMirrorDocument(TransactionCase):
    def test_mirror_keeps_taxes(self):
        original = self.env.ref("l10n_br_fiscal_mirror_document.demo_imported_document")
        action = original.action_create_mirror_document()
        mirror = original.mirror_document_ids
        self.assertEqual(action["res_id"], mirror.id)
        self.assertTrue(mirror.mirror_document)
        self.assertEqual(mirror.issuer, "company")
        self.assertEqual(mirror.original_document_id, original)
        self.assertEqual(original.mirror_document_count, 1)

        line = mirror.fiscal_line_ids
        self.assertEqual(line.icms_value, 324.0)
        self.assertEqual(line.icms_origin, "1")
        line.price_unit = 200.0
        self.assertEqual(line.icms_value, 324.0)

    def test_payment_mode_without_invoice(self):
        document = self.env.ref("l10n_br_nfe.demo_nfe_same_state")
        self.assertFalse(document.move_ids)
        self.assertEqual(document.nfe40_detPag.nfe40_tPag, "18")
        document.payment_mode_id = False
        self.assertEqual(document.nfe40_detPag.nfe40_tPag, "90")
