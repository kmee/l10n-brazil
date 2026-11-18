# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

import logging

from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    PROFIT_CALCULATION_PRESUMED,
    TAX_FRAMEWORK_SIMPLES,
)

from .common import AccountMoveBRCommon

_logger = logging.getLogger(__name__)


@tagged("post_install", "-at_install")
class TestSimplesSupplierCredit(AccountMoveBRCommon):
    """The credit that a supplier of the Simples Nacional passes (LC 123/2006,
    art. 23, paragraphs 1 and 2).

    CSOSN 101 and 201 pass the credit the supplier highlighted (vCredICMSSN):
    it is the ICMS to recover of the buyer of the normal regime when the
    destination gives the right to credit. CSOSN 102, 103, 300, 400 and 500 do
    not pass any. The credit comes out of the product line only when it goes to
    the ICMS to recover.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.configure_normal_company_taxes()
        cls.company = cls.company_data["company"]
        cls.company.profit_calculation = PROFIT_CALCULATION_PRESUMED
        cls.partner_a.tax_framework = TAX_FRAMEWORK_SIMPLES
        cls.operation = cls.env.ref("l10n_br_fiscal.fo_compras")

    def _bill(self, tax, cst, operation_line, credit=0.0, number="3001"):
        ref = self.env.ref
        document = self.env["l10n_br_fiscal.document"].create(
            {
                "fiscal_operation_id": self.operation.id,
                "document_type_id": ref("l10n_br_fiscal.document_55").id,
                "document_serie": "1",
                "document_number": number,
                "document_date": fields.Date.from_string("2026-11-10"),
                "issuer": "partner",
                "partner_id": self.partner_a.id,
                "fiscal_operation_type": "in",
                "imported_document": True,
            }
        )
        self.env["l10n_br_fiscal.document.line"].create(
            {
                "document_id": document.id,
                "name": "Simples supplier line",
                "product_id": self.product_a.id,
                "quantity": 1,
                "price_unit": 1000.0,
                "fiscal_operation_type": "in",
                "fiscal_operation_id": self.operation.id,
                "fiscal_operation_line_id": ref(f"l10n_br_fiscal.{operation_line}").id,
                "icmssn_tax_id": ref(f"l10n_br_fiscal.{tax}").id,
                "icms_cst_id": ref(f"l10n_br_fiscal.{cst}").id,
                "icmssn_base": 1000.0,
                "icmssn_percent": 2.0 if credit else 0.0,
                "icmssn_credit_value": credit,
            }
        )
        move_form = (
            self.env["account.move"]
            .sudo()
            .import_fiscal_document(document, move_type="in_invoice")
        )
        move = self.env["account.move"].sudo().browse(move_form.id)
        for line in move.line_ids:
            _logger.info(
                "SIMPLES %s %s %s debit=%.2f credit=%.2f tax=%s",
                cst,
                operation_line,
                line.account_id.code,
                line.debit,
                line.credit,
                line.tax_line_id.name,
            )
        return move

    @staticmethod
    def _icms_credit_lines(move):
        return move.line_ids.filtered(lambda line: line.tax_line_id)

    def _assert_balanced(self, move, total):
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0)
        self.assertAlmostEqual(move.amount_total, total)

    def test_csosn_101_resale_credits_the_icms(self):
        move = self._bill(
            "tax_icms_sn_com_credito",
            "cst_icmssn_101",
            "fo_compras_compras_comercializacao",
            credit=20.0,
        )
        self._assert_balanced(move, 1000.0)
        self.assertAlmostEqual(move.invoice_line_ids.balance, 980.0)
        credit = self._icms_credit_lines(move)
        self.assertAlmostEqual(sum(credit.mapped("debit")), 20.0)

    def test_csosn_101_use_and_consumption_has_no_credit(self):
        move = self._bill(
            "tax_icms_sn_com_credito",
            "cst_icmssn_101",
            "fo_compras_compras_uso_consumo",
            credit=20.0,
            number="3002",
        )
        self._assert_balanced(move, 1000.0)
        self.assertAlmostEqual(move.invoice_line_ids.balance, 1000.0)
        self.assertFalse(sum(self._icms_credit_lines(move).mapped("debit")))

    def test_csosn_102_passes_no_credit(self):
        move = self._bill(
            "tax_icms_sn_sem_credito",
            "cst_icmssn_102",
            "fo_compras_compras_comercializacao",
            number="3003",
        )
        self._assert_balanced(move, 1000.0)
        self.assertAlmostEqual(move.invoice_line_ids.balance, 1000.0)
        self.assertFalse(sum(self._icms_credit_lines(move).mapped("debit")))
