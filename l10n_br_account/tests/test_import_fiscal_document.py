# Copyright 2026 - TODAY KMEE - Luis Felipe Mileo <mileo@kmee.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from datetime import date, datetime

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common import AccountMoveBRCommon


@tagged("post_install", "-at_install")
class TestImportFiscalDocument(AccountMoveBRCommon):
    """Import an existing fiscal document into a brand new account.move.

    This is the code path used when the fiscal document exists before its
    invoice: imported XML, DUIMP declarations, service invoices captured
    from a PDF. It differs from button_import_fiscal_document, which
    imports into an existing move and is already covered by
    test_account_move_lc.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.configure_normal_company_taxes()
        cls.company = cls.company_data["company"]

    def _create_fiscal_document(self, **extra):
        document = self.env["l10n_br_fiscal.document"].create(
            {
                "company_id": self.company.id,
                "fiscal_operation_id": self.env.ref("l10n_br_fiscal.fo_compras").id,
                "fiscal_operation_type": "in",
                "document_type_id": self.env.ref("l10n_br_fiscal.document_55").id,
                "document_number": "123",
                "document_serie": "1",
                "issuer": "partner",
                "partner_id": self.partner_a.id,
                **extra,
            }
        )
        self.env["l10n_br_fiscal.document.line"].create(
            {
                "document_id": document.id,
                "name": "Import Test",
                "product_id": self.product_a.id,
                "fiscal_operation_id": document.fiscal_operation_id.id,
                "fiscal_operation_line_id": self.env.ref(
                    "l10n_br_fiscal.fo_compras_compras"
                ).id,
                "fiscal_operation_type": "in",
                "quantity": 1,
                "price_unit": 100.0,
            }
        )
        return document

    def test_import_keeps_the_emission_date_of_the_file(self):
        """The emission date of the imported document is not rewritten with
        the invoice date at midnight of the user timezone."""
        self.env.user.tz = "Europe/Brussels"
        emission = datetime(2026, 11, 17, 18, 0, 0)
        document = self._create_fiscal_document(
            document_date=emission, imported_document=True
        )
        move_form = self.env["account.move"].sudo().import_fiscal_document(document)
        move = self.env["account.move"].browse(move_form.id)
        self.assertEqual(move.invoice_date, date(2026, 11, 17))
        self.assertEqual(document.document_date, emission)

    def test_a_cancelled_or_denied_document_is_not_imported_into_a_bill(self):
        for state in ("cancelada", "denegada"):
            document = self._create_fiscal_document(state_edoc=state)
            with self.assertRaises(UserError):
                self.env["account.move"].import_fiscal_document(document)
            self.assertFalse(document.move_ids)

    def test_the_same_document_is_not_imported_into_two_bills(self):
        document = self._create_fiscal_document()
        move_form = self.env["account.move"].import_fiscal_document(document)
        move = self.env["account.move"].browse(move_form.id)
        with self.assertRaisesRegex(UserError, move.display_name):
            self.env["account.move"].import_fiscal_document(document)
        self.assertEqual(document.move_ids, move)
        # a cancelled bill does not hold the document
        move.button_cancel()
        self.env["account.move"].import_fiscal_document(document)

    def test_import_into_a_new_vendor_bill(self):
        """A vendor fiscal document is imported into a new vendor bill."""
        document = self._create_fiscal_document()
        move_form = self.env["account.move"].import_fiscal_document(document)
        move = self.env["account.move"].browse(move_form.id)
        self.assertEqual(move.move_type, "in_invoice")
        self.assertEqual(move.fiscal_document_id, document)
        self.assertEqual(move.partner_id, self.partner_a)
        self.assertEqual(move.document_serie, "1")
        self.assertEqual(len(move.invoice_line_ids), 1)
        self.assertEqual(
            move.invoice_line_ids.fiscal_document_line_id,
            document.fiscal_line_ids,
        )
