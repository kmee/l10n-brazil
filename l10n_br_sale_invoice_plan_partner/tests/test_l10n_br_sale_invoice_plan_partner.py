# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestL10nBrSaleInvoicePlanPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                allowed_company_ids=cls.company.ids,
                default_company_id=cls.company.id,
            )
        )
        cls.env.user.company_ids |= cls.company
        cls.env.user.company_id = cls.company
        # Taxpayer company of SP and individual non-taxpayer of MG
        cls.customer = cls.env.ref("l10n_br_base.res_partner_cliente1_sp")
        cls.payer_pf = cls.env.ref("l10n_br_base.res_partner_cliente10_mg")
        cls.goods = cls.env.ref("product.product_product_6")
        cls.goods.invoice_policy = "order"
        cls.service = cls.env.ref("l10n_br_fiscal.customized_development_sale")
        cls.operation = cls.company.sale_fiscal_operation_id
        # Companies withhold federal taxes on services, individuals do not
        profile = cls.env.ref("l10n_br_fiscal.partner_fiscal_profile_cnt")
        for xmlid in (
            "l10n_br_fiscal.tax_csll_wh_1",
            "l10n_br_fiscal.tax_pis_wh_0_65",
            "l10n_br_fiscal.tax_cofins_wh_3",
        ):
            tax = cls.env.ref(xmlid)
            cls.env["l10n_br_fiscal.tax.definition"].create(
                {
                    "fiscal_profile_id": profile.id,
                    "tax_group_id": tax.tax_group_id.id,
                    "tax_id": tax.id,
                    "state": "approved",
                    # With a company the definition applies to every profile
                    "company_id": False,
                    "service_type_ids": [Command.set(cls.service.service_type_id.ids)],
                }
            )

    def _order(self, partner, goods_qty, service_qty, plan=None):
        vals = {
            "partner_id": partner.id,
            "company_id": self.company.id,
            "fiscal_operation_id": self.operation.id,
            "order_line": [
                Command.create(
                    {
                        "product_id": product.id,
                        "product_uom_qty": qty,
                        "price_unit": price,
                        "fiscal_operation_id": self.operation.id,
                    }
                )
                for product, qty, price in (
                    (self.goods, goods_qty, 320.0),
                    (self.service, service_qty, 1000.0),
                )
            ],
        }
        if plan:
            vals.update(
                {
                    "use_invoice_plan": True,
                    "invoice_plan_mode": "payer",
                    "invoice_plan_ids": [
                        Command.create({"payer_partner_id": p.id, "percent": pct})
                        for p, pct in plan
                    ],
                }
            )
        order = self.env["sale.order"].create(vals)
        order.action_confirm()
        return order

    def _invoice_by_plan(self, order):
        self.env["sale.make.planned.invoice"].with_context(
            active_id=order.id, active_ids=order.ids, active_model="sale.order"
        ).create({}).create_invoices_by_plan()
        return order.invoice_ids

    def _fiscal(self, invoices, product):
        line = invoices.invoice_line_ids.filtered(lambda ln: ln.product_id == product)
        line.ensure_one()
        return {
            "partner": line.move_id.partner_id,
            "ind_final": line.move_id.ind_final,
            "operation_line": line.fiscal_operation_line_id,
            "cfop": line.cfop_id.code,
            "fiscal_taxes": line.fiscal_tax_ids,
            "taxes": line.tax_ids,
            "icms_destination": line.icms_destination_value,
            "withholding": line.amount_tax_withholding,
            "subtotal": line.price_subtotal,
        }

    def test_payer_invoice_matches_direct_order(self):
        order = self._order(
            self.customer, 4, 1, plan=[(self.customer, 50), (self.payer_pf, 50)]
        )
        invoices = self._invoice_by_plan(order)
        to_pf = invoices.filtered(lambda m: m.partner_id == self.payer_pf)
        to_customer = invoices - to_pf
        self.assertTrue(to_pf and to_customer)

        direct = self._order(self.payer_pf, 2, 0.5)._create_invoices()
        for product in (self.goods, self.service):
            payer_fiscal = self._fiscal(to_pf, product)
            direct_fiscal = self._fiscal(direct, product)
            if product == self.service:
                # A service document takes ind_final from the partner, while the
                # direct order copies the one of the order to its NFS-e.
                del payer_fiscal["ind_final"], direct_fiscal["ind_final"]
            self.assertEqual(
                payer_fiscal,
                direct_fiscal,
                f"{product.name}: payer invoice differs from a direct order",
            )
        # The share of the customer keeps the fiscal data of the order
        customer_goods = self._fiscal(to_customer, self.goods)
        order_goods = order.order_line.filtered(lambda ln: ln.product_id == self.goods)
        self.assertEqual(customer_goods["cfop"], order_goods.cfop_id.code)
        self.assertTrue(self._fiscal(to_customer, self.service)["withholding"])
        self.assertFalse(self._fiscal(to_pf, self.service)["withholding"])
