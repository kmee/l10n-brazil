# Copyright 2026 KMEE (https://www.kmee.com.br)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase


class TestNfeProductCustomerinfo(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.partner = cls.env.ref("l10n_br_base.res_partner_cliente1_sp")
        cls.other_partner = cls.env.ref("l10n_br_base.res_partner_cliente2_sp")
        cls.product = cls.env.ref("product.product_product_27")

    def _sale_line(self, partner):
        order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "fiscal_operation_id": self.env.ref("l10n_br_fiscal.fo_venda").id,
            }
        )
        return self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": self.product.id,
                "fiscal_operation_id": order.fiscal_operation_id.id,
            }
        )

    def test_sale_line_from_customerinfo(self):
        line = self._sale_line(self.partner)
        self.assertEqual(line.partner_product_code, "NTB-CORP-15")
        self.assertEqual(line.partner_product_name, "Notebook corporativo 15 polegadas")
        self.assertFalse(self._sale_line(self.other_partner).partner_product_code)

    def test_sale_line_onchange(self):
        line = self.env["sale.order.line"].new(
            {
                "order_id": self.env["sale.order"].new({"partner_id": self.partner.id}),
                "product_id": self.product.id,
            }
        )
        line._onchange_partner_product()
        self.assertEqual(line.partner_product_code, "NTB-CORP-15")

    def test_invoice_line_and_move_keep_the_partner_product(self):
        line = self._sale_line(self.partner)
        invoice_vals = line._prepare_invoice_line()
        self.assertEqual(invoice_vals["partner_product_code"], "NTB-CORP-15")
        picking_type = self.env["stock.picking.type"].search(
            [("code", "=", "outgoing")], limit=1
        )
        picking = self.env["stock.picking"].create(
            {
                "partner_id": self.partner.id,
                "picking_type_id": picking_type.id,
                "location_id": picking_type.default_location_src_id.id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            }
        )
        move = self.env["stock.move"].create(
            {
                "name": self.product.name,
                "picking_id": picking.id,
                "product_id": self.product.id,
                "product_uom_qty": 1,
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
            }
        )
        self.assertEqual(move.partner_product_code, "NTB-CORP-15")

    def test_nfe_export_uses_partner_product(self):
        line = self.env.ref("l10n_br_nfe.demo_nfe_line_same_state_1-2")
        export = {}
        line._export_fields_nfe_40_prod([], None, export)
        self.assertNotEqual(export["xProd"], "Notebook corporativo 15 polegadas")
        line.write(
            {
                "partner_product_code": "NTB-CORP-15\n",
                "partner_product_name": "Notebook corporativo 15 polegadas",
            }
        )
        export = {}
        line._export_fields_nfe_40_prod([], None, export)
        self.assertEqual(export["cProd"], "NTB-CORP-15")
        self.assertEqual(export["xProd"], "Notebook corporativo 15 polegadas")
