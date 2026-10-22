# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestSaleDeliveryCostsByTotal(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.env.user.company_ids |= cls.company
        cls.env.user.company_id = cls.company
        cls.product = cls.env.ref("product.product_product_6")

    def _create_order(self, order_vals=None):
        operation = self.env.ref("l10n_br_fiscal.fo_venda")
        operation_line = self.env.ref("l10n_br_fiscal.fo_venda_venda")
        vals = {
            "company_id": self.company.id,
            "partner_id": self.env.ref("l10n_br_base.res_partner_cliente1_sp").id,
            "fiscal_operation_id": operation.id,
            "force_compute_delivery_costs_by_total": True,
            "order_line": [
                (
                    0,
                    0,
                    {
                        "product_id": self.product.id,
                        "product_uom_qty": 1.0,
                        "price_unit": price,
                        "fiscal_operation_id": operation.id,
                        "fiscal_operation_line_id": operation_line.id,
                    },
                )
                for price in (1000.0, 1000.0, 1800.0)
            ],
        }
        vals.update(order_vals or {})
        return self.env["sale.order"].create(vals)

    def test_freight_typed_before_saving_lines_is_distributed(self):
        """Freight informed together with new lines is split proportionally
        to the line amounts, with the rounding rest on the last line."""
        order = self._create_order({"amount_freight_value": 100.0})
        self.assertEqual(
            [line.freight_value for line in order.order_line],
            [26.32, 26.32, 47.36],
        )
        self.assertAlmostEqual(order.amount_freight_value, 100.0)

    def test_freight_typed_in_form_before_saving_lines(self):
        """Same scenario through the sale order form, as the user does it:
        new lines, force costs by total, freight typed, then save."""
        self.env.user.groups_id |= self.env.ref("l10n_br_fiscal.group_user")
        self.env.user.groups_id |= self.env.ref("sales_team.group_sale_salesman")
        operation = self.env.ref("l10n_br_fiscal.fo_venda")
        order_form = Form(self.env["sale.order"])
        order_form.partner_id = self.env.ref("l10n_br_base.res_partner_cliente1_sp")
        order_form.fiscal_operation_id = operation
        for price in (1000.0, 1000.0, 1800.0):
            with order_form.order_line.new() as line_form:
                line_form.product_id = self.product
                line_form.product_uom_qty = 1.0
                line_form.price_unit = price
        order_form.force_compute_delivery_costs_by_total = True
        order_form.amount_freight_value = 100.0
        order = order_form.save()
        self.assertEqual(
            [line.freight_value for line in order.order_line],
            [26.32, 26.32, 47.36],
        )

    def test_freight_with_values_sent_by_the_web_client(self):
        """Reproduces the browser: the web client sends the order and its new
        lines in a single create(), and every line but the last one edited
        carries the fiscal amounts returned by the onchange. In that case
        price_gross is still empty when the freight inverse runs, so the
        freight must not depend on it."""
        operation = self.env.ref("l10n_br_fiscal.fo_venda")
        partner = self.env.ref("l10n_br_base.res_partner_cliente1_sp")
        # fields that the line form sends back with the onchange values
        onchange_fields = [
            "fiscal_type",
            "ncm_id",
            "nbm_id",
            "cest_id",
            "nbs_id",
            "service_type_id",
            "icms_origin",
            "tax_icms_or_issqn",
            "fiscal_amount_untaxed",
            "fiscal_amount_tax",
            "fiscal_amount_total",
        ]
        lines = []
        for price, sent_by_onchange in (
            (1000.0, True),
            (1000.0, True),
            (1800.0, False),
        ):
            vals = {
                "product_id": self.product.id,
                "product_uom_qty": 1.0,
                "price_unit": price,
                "fiscal_operation_id": operation.id,
            }
            if sent_by_onchange:
                virtual = self.env["sale.order.line"].new(
                    dict(vals, company_id=self.company.id, partner_id=partner.id)
                )
                for fname in onchange_fields:
                    vals[fname] = virtual._fields[fname].convert_to_write(
                        virtual[fname], virtual
                    )
            lines.append((0, 0, vals))
        order = self.env["sale.order"].create(
            {
                "company_id": self.company.id,
                "partner_id": partner.id,
                "fiscal_operation_id": operation.id,
                "force_compute_delivery_costs_by_total": True,
                "amount_freight_value": 100.0,
                "order_line": lines,
            }
        )
        self.assertEqual(
            [line.freight_value for line in order.order_line],
            [26.32, 26.32, 47.36],
        )
        self.assertAlmostEqual(order.amount_freight_value, 100.0)
