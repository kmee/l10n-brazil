# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_br_sale.tests.tools import load_sale_fixture_files


@tagged("post_install", "-at_install")
class TestL10nBrSalePaymentInstallment(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.env.user.company_ids |= cls.company
        cls.env.user.company_id = cls.company
        cls.partner = cls.env.ref("l10n_br_base.res_partner_cliente1_sp")
        # FURN_8855 has IPI, a tax that is not included in the price.
        cls.product = cls.env.ref("product.product_product_27")
        cls.fiscal_operation = cls.env.ref("l10n_br_fiscal.fo_venda")
        operation_line = cls.fiscal_operation.line_definition(
            cls.company, cls.partner, cls.product
        )
        order_values = {}
        if "stock.warehouse" in cls.env:
            # The demo company has no warehouse when the stock app is installed.
            warehouse = cls.env["stock.warehouse"].search(
                [("company_id", "=", cls.company.id)], limit=1
            ) or cls.env["stock.warehouse"].create(
                {"name": "Test", "code": "TSTPI", "company_id": cls.company.id}
            )
            order_values["warehouse_id"] = warehouse.id
        cls.order = cls.env["sale.order"].create(
            {
                **order_values,
                "company_id": cls.company.id,
                "partner_id": cls.partner.id,
                "fiscal_operation_id": cls.fiscal_operation.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": cls.product.id,
                            "product_uom_qty": qty,
                            "price_unit": 100.0,
                            "fiscal_operation_id": cls.fiscal_operation.id,
                            "fiscal_operation_line_id": operation_line.id,
                        }
                    )
                    for qty in (10.0, 2.0)
                ],
            }
        )
        cls.line_big, cls.line_small = cls.order.order_line
        cls.plan_line = cls.env["payment.installment.plan"].create(
            {
                "name": "Up to 12x",
                "line_ids": [
                    Command.create(
                        {
                            "installments": 12,
                            "interest_rate": 10.0,
                            "interest_charged_by": "merchant",
                        }
                    )
                ],
            }
        ).line_ids

    def _shares(self):
        return self.order.order_line.mapped("installment_surcharge_value")

    def test_interest_goes_to_the_other_costs_of_the_goods(self):
        order = self.order
        line = order._set_installment_surcharge(self.plan_line, 120.0)
        self.assertFalse(line)
        self.assertFalse(order._get_installment_surcharge_lines())
        big, small = self._shares()
        self.assertTrue(big and small)
        # The first line has five times the gross amount of the second one.
        self.assertAlmostEqual(big, small * 5, delta=0.02)
        self.assertEqual(self.line_big.other_value, big)
        self.assertEqual(self.line_small.other_value, small)
        self.assertAlmostEqual(order.amount_other_value, big + small, places=2)

    def test_total_grows_by_the_interest_taxes_included(self):
        """The IPI is computed on the other costs too: the other costs are what
        makes the payer pay the interest shown, not a cent more."""
        order = self.order
        total_before = order.amount_total
        order._set_installment_surcharge(self.plan_line, 120.0)
        added = order.amount_total - total_before
        self.assertAlmostEqual(added, 120.0, delta=0.01)
        self.assertLess(sum(self._shares()), 120.0)
        self.assertAlmostEqual(order.installment_surcharge_total, added, places=2)
        self.assertAlmostEqual(order.installment_surcharge_amount, added, places=2)
        self.assertAlmostEqual(
            order._get_installment_base_amount(), total_before, places=2
        )

    def test_rounding_difference_goes_to_the_last_line(self):
        shares = self.order._distribute_installment_surcharge(100.0)
        self.assertEqual(shares[self.line_big], 83.33)
        self.assertEqual(shares[self.line_small], 16.67)

    def test_choosing_again_replaces_the_interest(self):
        order = self.order
        total_before = order.amount_total
        order._set_installment_surcharge(self.plan_line, 120.0)
        order._set_installment_surcharge(self.plan_line, 60.0)
        self.assertAlmostEqual(order.amount_total - total_before, 60.0, delta=0.01)
        order._set_installment_surcharge(self.plan_line, 0.0)
        self.assertEqual(self.line_big.other_value, 0.0)
        self.assertEqual(self.line_small.other_value, 0.0)
        self.assertEqual(self._shares(), [0.0, 0.0])
        self.assertAlmostEqual(order.amount_total, total_before, places=2)
        self.assertEqual(order.installment_surcharge_total, 0.0)

    def test_other_costs_the_order_already_had_are_kept(self):
        self.line_big.other_value = 10.0
        self.order._set_installment_surcharge(self.plan_line, 120.0)
        self.assertAlmostEqual(
            self.line_big.other_value, 10.0 + self._shares()[0], places=2
        )
        self.order._set_installment_surcharge(self.plan_line, 0.0)
        self.assertEqual(self.line_big.other_value, 10.0)

    def test_costs_informed_by_total(self):
        self.company.delivery_costs = "total"
        order = self.order
        order.amount_other_value = 30.0
        total_before = order.amount_total
        order._set_installment_surcharge(self.plan_line, 120.0)
        self.assertAlmostEqual(order.amount_total - total_before, 120.0, delta=0.01)
        self.assertAlmostEqual(
            order.amount_other_value, 30.0 + sum(self._shares()), places=2
        )
        self.assertAlmostEqual(
            self.line_big.other_value + self.line_small.other_value,
            order.amount_other_value,
            places=2,
        )
        order._set_installment_surcharge(self.plan_line, 0.0)
        self.assertAlmostEqual(order.amount_other_value, 30.0, places=2)

    def test_copied_order_does_not_inherit_the_interest(self):
        self.line_big.other_value = 10.0
        self.order._set_installment_surcharge(self.plan_line, 120.0)
        copied = self.order.copy()
        self.assertEqual(
            [round(v, 2) for v in copied.order_line.mapped("other_value")], [10.0, 0.0]
        )
        self.assertEqual(copied.installment_surcharge_total, 0.0)

    def test_order_with_goods_can_take_the_interest(self):
        self.assertTrue(self.order._can_take_installment_surcharge())

    def test_order_with_services_cannot_take_the_interest(self):
        if not self.env.ref(
            "l10n_br_sale.main_so_only_services", raise_if_not_found=False
        ):
            load_sale_fixture_files(self.env)
        for xmlid in (
            "l10n_br_sale.main_so_only_services",
            "l10n_br_sale.main_so_product_service",
        ):
            order = self.env.ref(xmlid)
            order.state = "draft"
            self.assertFalse(order._can_take_installment_surcharge(), xmlid)

    def test_order_without_fiscal_operation_gets_the_generic_line(self):
        order = self.env["sale.order"].create(
            {
                "company_id": self.company.id,
                "partner_id": self.partner.id,
                "fiscal_operation_id": False,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1.0,
                            "price_unit": 100.0,
                        }
                    )
                ],
            }
        )
        self.plan_line.plan_id.surcharge_product_id = self.env.ref(
            "sale_payment_installment.product_installment_surcharge"
        )
        line = order._set_installment_surcharge(self.plan_line, 10.0)
        self.assertTrue(line.is_installment_surcharge)

    def test_interest_follows_the_order_to_the_invoice(self):
        order = self.order
        order._set_installment_surcharge(self.plan_line, 120.0)
        order.action_confirm()
        invoice = order._create_invoices()
        self.assertAlmostEqual(
            sum(invoice.invoice_line_ids.mapped("other_value")),
            sum(self._shares()),
            places=2,
        )
        self.assertAlmostEqual(
            invoice.amount_other_value, order.amount_other_value, places=2
        )
        self.assertAlmostEqual(invoice.amount_total, order.amount_total, places=2)
