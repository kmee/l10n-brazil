# Copyright (C) 2026  Luis Felipe Mileo - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo.exceptions import UserError
from odoo.tests import TransactionCase
from odoo.tools.translate import _ as translate


class TestDocumentImportCheck(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.product = cls.env["product.product"].create(
            {"name": "Amostra Teste", "uom_id": cls.env.ref("uom.product_uom_unit").id}
        )
        cls.document = cls.env["l10n_br_fiscal.document"].create(
            {
                "document_type_id": cls.env.ref(
                    "l10n_br_fiscal.document_55_serie_1"
                ).id,
                "fiscal_operation_type": "in",
                "imported_document": True,
            }
        )
        cls.line = cls.env["l10n_br_fiscal.document.line"].create(
            {
                "document_id": cls.document.id,
                "name": "Amostra gratis",
                "product_id": cls.product.id,
                "uom_id": cls.env.ref("uom.product_uom_unit").id,
                "quantity": 1.0,
                "price_unit": 0.0,
            }
        )

    def test_free_line_is_allowed(self):
        """A 100% free line (zero unit price AND zero amounts, e.g. a
        bonification or free sample declared with vUnCom=0) must not block
        the account move generation."""
        self.assertFalse(self.line.fiscal_amount_total)
        self.document._check_document_import()  # must not raise

    def test_zero_price_with_amounts_is_blocked(self):
        """A zero unit price on a line that still carries amounts is an
        unresolved de-para (inconsistent data) and must keep blocking."""
        self.line.freight_value = 100.0
        self.assertTrue(self.line.fiscal_amount_total)
        with self.assertRaises(UserError):
            self.document._check_document_import()

    def test_missing_product_is_blocked(self):
        self.line.price_unit = 10.0
        self.line.product_id = False
        with self.assertRaises(UserError):
            self.document._check_document_import()

    def test_a_line_not_reviewed_blocks_the_bill(self):
        """The bill of an imported document rests on reviewed lines only: a
        line that is just a suggestion of the import (or has no product yet)
        refuses the bill, however it is asked for."""
        self.line.price_unit = 10.0
        for state in ("matched", "pending"):
            self.line.import_state = state
            with self.assertRaisesRegex(UserError, "not resolved yet"):
                self.document._check_document_import()
            with self.assertRaisesRegex(UserError, "not reviewed"):
                self.env["account.move"].import_fiscal_document(self.document)
            with self.assertRaisesRegex(UserError, "not resolved yet"):
                self.document.action_generate_account_move()
        self.line.import_state = "resolved"
        self.document._check_document_import()  # must not raise

    def test_confirming_an_imported_document_needs_the_review(self):
        """The confirmation takes a partner document to authorized, and so to
        the books: it refuses the lines that were not resolved."""
        self.line.price_unit = 10.0
        self.line.import_state = "matched"
        with self.assertRaisesRegex(UserError, "not reviewed"):
            self.document.action_document_confirm()

    def test_the_refusal_is_in_portuguese(self):
        """The header of the message that refuses the bill, and the reason of each
        line, are in Portuguese for the user."""
        self.env["res.lang"]._activate_lang("pt_BR")
        self.env["ir.module.module"].search(
            [("name", "=", "l10n_br_account")]
        )._update_translations(["pt_BR"])
        self.env = self.env(context=dict(self.env.context, lang="pt_BR"))
        header = translate(
            "The document cannot be imported due to incomplete lines:\n%s"
        )
        self.assertIn("linhas incompletas", header)
        self.assertIn("nenhum produto", translate("- %s: no product matched."))
        self.assertIn("sem quantidade", translate("- %s: no quantity."))
