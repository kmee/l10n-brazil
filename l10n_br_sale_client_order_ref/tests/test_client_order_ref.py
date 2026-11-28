# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_br_sale.hooks import sale_set_journal_in_fiscal_operation
from odoo.addons.l10n_br_stock_account.tests.common import TestBrPickingInvoicingCommon


@tagged("post_install", "-at_install")
class TestClientOrderRef(TestBrPickingInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.company"].search(
            [("sale_invoicing_policy", "=", "sale_order")]
        ).sale_invoicing_policy = "stock_picking"
        sale_set_journal_in_fiscal_operation(cls.env)
        cls.fo_venda = cls.env.ref("l10n_br_fiscal.fo_venda")
        cls.fo_venda.journal_id = cls.op_simples_remessa.journal_id
        cls.product = cls.env["product.product"].create(
            {
                "name": "Luminaria de Embutir 18W",
                "type": "consu",
                "is_storable": True,
                "invoice_policy": "delivery",
                "lst_price": 100.0,
            }
        )
        cls.partner = cls.env.ref("l10n_br_base.res_partner_akretion")

    def _create_sale_order(self, client_order_ref, line_refs):
        return self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "fiscal_operation_id": self.fo_venda.id,
                "client_order_ref": client_order_ref,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 2,
                            "price_unit": 100.0,
                            "client_order_ref": line_ref,
                            "fiscal_operation_id": self.fo_venda.id,
                        }
                    )
                    for line_ref in line_refs
                ],
            }
        )

    def test_picking_invoice(self):
        order = self._create_sale_order("PC-9001", ["PC-9001", "PC-9001-02"])
        order.action_confirm()
        picking = order.picking_ids
        picking.set_to_be_invoiced()
        self.picking_move_state(picking)
        invoice = self.create_invoice_wizard(picking)
        document = invoice.fiscal_document_id
        self.assertEqual(invoice.ref, "PC-9001")
        self.assertEqual(document.sale_id, order)
        self.assertEqual(invoice.sale_id, order)
        self.assertEqual(document.client_order_ref, "PC-9001, PC-9001-02")
        document._document_comment()
        self.assertIn(
            "Referência do cliente: PC-9001, PC-9001-02",
            document.customer_additional_data,
        )

    def test_document_without_sale(self):
        document = self.env["l10n_br_fiscal.document"].create(
            {"client_order_ref": "REF-MANUAL"}
        )
        self.assertEqual(document.client_order_ref, "REF-MANUAL")
        self.assertFalse(document.sale_id)
