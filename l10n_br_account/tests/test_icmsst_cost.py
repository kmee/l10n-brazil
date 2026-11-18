# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    PROFIT_CALCULATION_PRESUMED,
    TAX_FRAMEWORK_NORMAL,
)

from .common import AccountMoveBRCommon


@tagged("post_install", "-at_install")
class TestIcmsStCost(AccountMoveBRCommon):
    """The ICMS ST the supplier charges on a purchase is cost, always.

    It is the same rule of the cost of the stock (``_stock_cost_add_value_fields``
    adds it for every destination): the vendor bill books no ICMS ST to recover
    and the value stays in the product line, for use and consumption, assets
    and resale alike.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.configure_normal_company_taxes()
        cls.company = cls.company_data["company"]
        cls.company.profit_calculation = PROFIT_CALCULATION_PRESUMED
        cls.partner_a.tax_framework = TAX_FRAMEWORK_NORMAL
        cls.operation = cls.env.ref("l10n_br_fiscal.fo_compras")

    def _bill(self, operation_line, number):
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
                "name": "ST line",
                "product_id": self.product_a.id,
                "quantity": 1,
                "price_unit": 1000.0,
                "fiscal_operation_type": "in",
                "fiscal_operation_id": self.operation.id,
                "fiscal_operation_line_id": ref(f"l10n_br_fiscal.{operation_line}").id,
                "icmsst_tax_id": ref("l10n_br_fiscal.tax_icmsst_29_43").id,
                "icmsst_base": 1000.0,
                "icmsst_percent": 5.0,
                "icmsst_value": 50.0,
            }
        )
        move_form = (
            self.env["account.move"]
            .sudo()
            .import_fiscal_document(document, move_type="in_invoice")
        )
        return self.env["account.move"].sudo().browse(move_form.id)

    def test_the_icmsst_stays_in_the_cost_of_every_destination(self):
        for number, operation_line in enumerate(
            (
                "fo_compras_compras_uso_consumo",
                "fo_compras_compras_ativo",
                "fo_compras_compras_comercializacao",
            ),
            start=3100,
        ):
            move = self._bill(operation_line, str(number))
            line = move.invoice_line_ids
            self.assertEqual(line.icmsst_value, 50.0, operation_line)
            st_lines = move.line_ids.filtered(
                lambda ml: ml.tax_line_id.tax_group_id.fiscal_tax_group_id.tax_domain
                == "icmsst"
            )
            self.assertFalse(st_lines, f"{operation_line}: no ICMS ST to recover")
            self.assertAlmostEqual(
                sum(move.line_ids.mapped("balance")), 0.0, msg=operation_line
            )
            payable = move.line_ids.filtered(
                lambda ml: ml.account_id.account_type == "liability_payable"
            )
            self.assertAlmostEqual(
                -sum(payable.mapped("balance")),
                line.fiscal_amount_total,
                msg=operation_line,
            )
