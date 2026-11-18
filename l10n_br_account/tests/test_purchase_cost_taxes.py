# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo.tests import Form, tagged

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    PROFIT_CALCULATION_PRESUMED,
    PROFIT_CALCULATION_REAL,
    TAX_FRAMEWORK_NORMAL,
)

from .common import AccountMoveBRCommon


@tagged("post_install", "-at_install")
class TestPurchaseCostTaxes(AccountMoveBRCommon):
    """The creditability map rules the vendor bill with or without the flag.

    A purchase for use and consumption or for the fixed assets does not give
    the ICMS credit in the month of the entry (LC 87/1996, art. 33, I and
    II), and PIS/COFINS only credit in the Lucro Real: whatever the operation
    says about ``deductible_taxes``, the ledger of those taxes books no
    credit and the value stays in the cost of the product line.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.configure_normal_company_taxes()
        cls.fo_compras = cls.env.ref("l10n_br_fiscal.fo_compras")
        cls.fo_compras.deductible_taxes = False
        cls.partner_a.tax_framework = TAX_FRAMEWORK_NORMAL
        cls.env.company.write(
            {
                "profit_calculation": PROFIT_CALCULATION_PRESUMED,
                "is_industry": False,
                "ripi": False,
            }
        )

    def _bill(self, operation_line, number="123", price_and_quantity=None):
        move = self.init_invoice(
            "in_invoice",
            products=[self.product_a],
            document_type=self.env.ref("l10n_br_fiscal.document_55"),
            fiscal_operation=self.fo_compras,
            fiscal_operation_lines=[self.env.ref(f"l10n_br_fiscal.{operation_line}")],
            document_serie="1",
            document_number=number,
        )
        if price_and_quantity:
            price, quantity = price_and_quantity
            with Form(move) as form:
                with form.invoice_line_ids.edit(0) as line_form:
                    line_form.price_unit = price
                    line_form.quantity = quantity
        return move

    @staticmethod
    def _tax_lines(move, domain):
        return move.line_ids.filtered(
            lambda line: line.tax_line_id.tax_group_id.fiscal_tax_group_id.tax_domain
            == domain
        )

    def _assert_balanced_at_the_total(self, move):
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0)
        self.assertAlmostEqual(
            move.amount_total, move.fiscal_document_id.fiscal_amount_total
        )
        payable = move.line_ids.filtered(
            lambda line: line.account_id.account_type == "liability_payable"
        )
        self.assertAlmostEqual(-sum(payable.mapped("balance")), move.amount_total)

    def _cost_case(self, operation_line):
        """Bill for a destination without credit, and the resale control."""
        control = self._bill("fo_compras_compras", number="120")
        bill = self._bill(operation_line, number="121")
        line = bill.invoice_line_ids
        self.assertGreater(line.icms_value, 0)
        self.assertFalse(self._tax_lines(bill, "icms"), "no ICMS to recover")
        self.assertFalse(self._tax_lines(bill, "pis"))
        self.assertFalse(self._tax_lines(bill, "cofins"))
        self._assert_balanced_at_the_total(bill)
        # the ICMS is inside the product line: the control line is the same
        # purchase net of the ICMS it recovers
        self.assertAlmostEqual(
            line.balance, control.invoice_line_ids.balance + line.icms_value
        )
        self.assertAlmostEqual(line.balance, line.fiscal_amount_total)
        return bill

    def test_use_and_consumption_without_the_flag(self):
        bill = self._cost_case("fo_compras_compras_uso_consumo")
        self.assertEqual(bill.state, "draft")
        bill.action_post()
        self.assertEqual(bill.state, "posted")
        self.assertFalse(self._tax_lines(bill, "icms"))

    def test_fixed_asset_without_the_flag(self):
        self._cost_case("fo_compras_compras_ativo")

    def test_resale_control_keeps_the_credit(self):
        bill = self._bill("fo_compras_compras")
        icms = self._tax_lines(bill, "icms")
        self.assertTrue(icms)
        self.assertGreater(bill.invoice_line_ids.icms_value, 0)
        self.assertAlmostEqual(
            sum(icms.mapped("debit")), bill.invoice_line_ids.icms_value
        )
        self._assert_balanced_at_the_total(bill)

    def test_the_flag_changes_nothing_for_the_cost_taxes(self):
        without_flag = self._bill("fo_compras_compras_uso_consumo", number="130")
        self.fo_compras.deductible_taxes = True
        with_flag = self._bill("fo_compras_compras_uso_consumo", number="131")
        self.assertFalse(self._tax_lines(with_flag, "icms"))
        self.assertAlmostEqual(
            with_flag.invoice_line_ids.balance,
            without_flag.invoice_line_ids.balance,
        )
        self._assert_balanced_at_the_total(with_flag)

    def test_ipi_by_fora_without_credit_is_balanced(self):
        bill = self._bill("fo_compras_compras_uso_consumo")
        line = bill.invoice_line_ids
        self.assertGreater(line.ipi_value, 0)
        ipi_taxes = line.tax_ids.filtered(lambda tax: "IPI" in tax.name)
        self.assertTrue(ipi_taxes)
        self.assertTrue(all(tax.no_credit for tax in ipi_taxes))
        self.assertFalse(self._tax_lines(bill, "ipi").filtered("balance"))
        self._assert_balanced_at_the_total(bill)

    def test_pis_cofins_credit_only_in_the_lucro_real(self):
        presumed = self._bill("fo_compras_compras", number="140")
        self.assertFalse(self._tax_lines(presumed, "pis"))
        self.assertFalse(self._tax_lines(presumed, "cofins"))
        self.env.company.write(
            {
                "profit_calculation": PROFIT_CALCULATION_REAL,
                "is_industry": True,
                "ripi": True,
            }
        )
        real = self._bill("fo_compras_compras", number="141")
        self.assertTrue(self._tax_lines(real, "pis"))
        self.assertTrue(self._tax_lines(real, "cofins"))
        self._assert_balanced_at_the_total(real)
        # the use and consumption of the Lucro Real has no ICMS credit either
        consumption = self._bill("fo_compras_compras_uso_consumo", number="142")
        self.assertFalse(self._tax_lines(consumption, "icms"))
        self._assert_balanced_at_the_total(consumption)

    def test_rounding_of_a_bill_with_cents(self):
        for number, operation_line in enumerate(
            (
                "fo_compras_compras_uso_consumo",
                "fo_compras_compras_ativo",
                "fo_compras_compras",
            ),
            start=150,
        ):
            bill = self._bill(
                operation_line, number=str(number), price_and_quantity=(333.37, 3)
            )
            self._assert_balanced_at_the_total(bill)
