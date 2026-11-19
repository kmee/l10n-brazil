# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal_dfe_import.tests.common import (
    KEY_1,
    KEY_2,
    DfeImportCase,
)


class TestGenerateInvoice(DfeImportCase):
    def setUp(self):
        super().setUp()
        documents, _errors = self.Document.dfe_import_files(
            [("nfe.xml", self._xml(KEY_1))]
        )
        self.document = documents
        self.document.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")

    def test_unresolved_line_refuses_the_invoice(self):
        line = self.document.fiscal_line_ids
        line.product_id = self.env["product.product"].create({"name": "Suggestion"})
        line.uom_id = self.env.ref("uom.product_uom_unit")
        self.document._init_import_states()

        with self.assertRaisesRegex(UserError, "Resolve the lines"):
            self.document.action_generate_invoice()

    def test_resolved_lines_generate_the_invoice(self):
        product = self.env["product.product"].create({"name": "Reviewed product"})
        line = self.document.fiscal_line_ids
        line._apply_import_depara(
            product=product,
            uom=self.env.ref("uom.product_uom_unit"),
            fiscal_operation=self.env.ref("l10n_br_fiscal.fo_compras"),
        )

        action = self.document.action_generate_invoice()

        move = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(move.fiscal_document_id, self.document)
        self.assertEqual(move.move_type, "in_invoice")

    def test_vendor_bill_upload_uses_the_import_window(self):
        attachment = self.env["ir.attachment"].create(
            {"name": "nfe.xml", "raw": self._xml(KEY_2)}
        )
        journal = self.env["account.journal"].search(
            [("type", "=", "purchase")], limit=1
        )

        action = journal.create_document_from_attachment([attachment.id])

        self.assertEqual(action["res_model"], "l10n_br_fiscal.document")
        self.assertEqual(action["res_id"], self._imported(KEY_2).id)
