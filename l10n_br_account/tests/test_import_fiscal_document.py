# Copyright 2026 - TODAY KMEE - Luis Felipe Mileo <mileo@kmee.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import json
from datetime import date, datetime
from unittest import mock

from lxml import etree

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
        for number, state in (("901", "cancelada"), ("902", "denegada")):
            document = self._create_fiscal_document(
                state_edoc=state, document_number=number
            )
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

    def test_a_cancelled_bill_frees_the_document_of_the_supplier(self):
        """Cancelling the bill does not cancel the note of the supplier: the
        note keeps its state and can be invoiced again."""
        document = self._create_fiscal_document()
        state = document.state_edoc
        move_form = self.env["account.move"].import_fiscal_document(document)
        move = self.env["account.move"].browse(move_form.id)
        move.button_cancel()
        self.assertEqual(move.state, "cancel")
        self.assertEqual(document.state_edoc, state)
        self.assertFalse(document._import_block_reason())
        again_form = self.env["account.move"].import_fiscal_document(document)
        again = self.env["account.move"].browse(again_form.id)
        self.assertNotEqual(again, move)
        self.assertEqual(again.fiscal_document_id, document)
        again.button_cancel()
        again.button_draft()
        self.assertEqual(document.state_edoc, state)

    def test_a_cancelled_bill_cancels_the_document_of_the_company(self):
        """The control: the note the company issued follows its invoice."""
        document = self._create_fiscal_document()
        move_form = self.env["account.move"].import_fiscal_document(document)
        move = self.env["account.move"].browse(move_form.id)
        document.issuer = "company"
        model = type(self.env["l10n_br_fiscal.document"])
        with mock.patch.object(model, "action_document_cancel") as cancel_document:
            move.button_cancel()
        cancel_document.assert_called_once()

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

    def test_the_generate_button_follows_the_active_invoice(self):
        """A cancelled invoice frees the document: the button to generate the
        invoice shows again, while the counter keeps counting the cancelled."""
        document = self._create_fiscal_document(imported_document=True)
        self.assertFalse(document.has_active_move)
        move_form = self.env["account.move"].sudo().import_fiscal_document(document)
        move = self.env["account.move"].sudo().browse(move_form.id)
        self.assertTrue(document.has_active_move)
        move.button_cancel()
        self.assertFalse(document.has_active_move)
        self.assertEqual(document.move_count, 1)
        view = document.get_view(self.env.ref("l10n_br_fiscal.document_form").id)
        button = etree.fromstring(view["arch"]).xpath(
            "//button[@name='action_generate_account_move']"
        )[0]
        invisible = json.loads(button.get("modifiers"))["invisible"]
        self.assertIn("has_active_move", json.dumps(invisible))
        self.assertNotIn("move_count", json.dumps(invisible))
