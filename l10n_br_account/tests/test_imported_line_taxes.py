# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    TAX_FRAMEWORK_NORMAL,
    TAX_FRAMEWORK_SIMPLES,
)

from .common import AccountMoveBRCommon


@tagged("post_install", "-at_install")
class TestImportedLineTaxes(AccountMoveBRCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document_type_55 = cls.env.ref("l10n_br_fiscal.document_55")
        cls.operation = cls.env.ref("l10n_br_fiscal.fo_compras")
        cls.operation_line = cls.env.ref("l10n_br_fiscal.fo_compras_compras")

    def _import_document_with_taxes_from_a_file(self, line_vals=None):
        document = self.env["l10n_br_fiscal.document"].create(
            {
                "fiscal_operation_id": self.operation.id,
                "document_type_id": self.document_type_55.id,
                "document_serie": "1",
                "document_number": "4953",
                "document_date": fields.Date.from_string("2026-08-17"),
                "issuer": "partner",
                "partner_id": self.partner_a.id,
                "fiscal_operation_type": "in",
                "imported_document": True,
            }
        )
        self.env["l10n_br_fiscal.document.line"].create(
            {
                "document_id": document.id,
                "name": "Imported purchase line",
                "product_id": self.product_a.id,
                "quantity": 39,
                "price_unit": 100.0,
                "fiscal_operation_type": "in",
                "fiscal_operation_id": self.operation.id,
                "fiscal_operation_line_id": self.operation_line.id,
                "icms_tax_id": self.env.ref("l10n_br_fiscal.tax_icms_nt").id,
                "icms_base": 3900.0,
                "icms_percent": 12.0,
                "icms_value": 468.0,
                "ipi_tax_id": self.env.ref("l10n_br_fiscal.tax_ipi_6_5").id,
                "ipi_base": 3900.0,
                "ipi_percent": 9.75,
                "ipi_value": 380.25,
                **(line_vals or {}),
            }
        )
        move_form = (
            self.env["account.move"]
            .sudo()
            .import_fiscal_document(document, move_type="in_invoice")
        )
        return document, self.env["account.move"].sudo().browse(move_form.id)

    def _tax_amounts(self, move):
        tax_lines = move.line_ids.filtered(lambda line: line.display_type == "tax")
        return {
            line.tax_line_id.tax_group_id.fiscal_tax_group_id.tax_domain: line.debit
            for line in tax_lines
        }

    def test_the_tax_lines_carry_the_values_of_the_file(self):
        """A regular supplier passes the credit: the tax lines carry the
        values of the file."""
        self.partner_a.tax_framework = TAX_FRAMEWORK_NORMAL
        _document, move = self._import_document_with_taxes_from_a_file()
        self.assertEqual(self._tax_amounts(move), {"icms": 468.0, "ipi": 380.25})
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0)

    def test_a_supplier_of_the_simples_without_credit_passes_no_credit(self):
        """CSOSN 102 (and 103, 300, 400, 500) passes no credit (LC 123/2006,
        art. 23): the taxes of the file stay in the cost of the product line.
        The CSOSN 101 and 201, that pass the credit, are in
        test_simples_supplier_credit."""
        self.partner_a.tax_framework = TAX_FRAMEWORK_SIMPLES
        _document, move = self._import_document_with_taxes_from_a_file(
            {"icms_cst_id": self.env.ref("l10n_br_fiscal.cst_icmssn_102").id}
        )
        self.assertEqual(self._tax_amounts(move).get("icms", 0.0), 0.0)
        self.assertEqual(self._tax_amounts(move).get("ipi", 0.0), 0.0)
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0)
        self.assertAlmostEqual(move.invoice_line_ids.balance, 4280.25)

    def test_the_payment_term_of_an_imported_document_matches_the_file(self):
        document, move = self._import_document_with_taxes_from_a_file()
        payment_term_lines = move.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )

        self.assertEqual(sum(payment_term_lines.mapped("credit")), 4280.25)
        self.assertEqual(document.amount_financial_total, 4280.25)
