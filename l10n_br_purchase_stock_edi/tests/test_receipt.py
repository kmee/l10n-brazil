# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase


class TestImportReceipt(TransactionCase):
    """The sample note of the demo data: it declares an order of 6 units of a
    stockable product and brings 5 (see ``demo/purchase_stock_edi_demo.xml``)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.order = cls.env.ref("l10n_br_purchase_stock_edi.demo_order_stock")
        cls.order_line = cls.order.order_line
        cls.document = cls.env["l10n_br_fiscal.document"].search(
            [
                ("document_number", "=", "3001"),
                ("partner_id", "=", cls.env.ref("l10n_br_base.res_partner_dell").id),
            ],
            limit=1,
        )
        cls.line = cls.document.fiscal_line_ids
        cls.bill = cls.document.move_ids
        cls.move = cls.order_line.move_ids

    def test_receipt_move_is_the_origin(self):
        self.assertEqual(self.line.import_origin_state, "resolved")
        self.assertEqual(self.line.import_purchase_line_id, self.order_line)
        self.assertEqual(self.line.import_stock_move_id, self.move)
        self.assertEqual(self.document.import_picking_ids, self.move.picking_id)
        self.assertEqual(self.bill.import_picking_count, 1)

    def test_fill_receipt_from_the_document(self):
        self.assertEqual(self.move.quantity, 6)
        self.bill.action_fill_import_receipts()
        self.assertEqual(self.move.quantity, 5)
        self.assertNotEqual(self.move.state, "done")

    def test_fill_receipt_keeps_what_was_picked(self):
        self.move.write({"quantity": 4, "picked": True})
        self.bill.action_fill_import_receipts()
        self.assertEqual(self.move.quantity, 4)

    def test_awaiting_receipt_is_not_a_divergence(self):
        self.assertTrue(self.line.import_awaiting_receipt)
        self.assertFalse(self.line.import_divergent)
        self.assertEqual(self.line.import_ordered_qty, 6)
        self.assertFalse(self.bill.purchase_divergent)

    def test_price_out_of_the_tolerance_is_divergent(self):
        self.line.price_unit = 150.0
        self.assertEqual(self.line.import_price_difference, 10.0)
        self.assertTrue(self.line.import_divergent)
        self.assertTrue(self.document.import_divergent)
        # a tolerance of the company covers the difference
        self.line.company_id.purchase_price_tolerance = 10.0
        self.assertFalse(self.line.import_divergent)

    def test_quantity_over_the_received_is_divergent(self):
        self.move.write({"quantity": 6, "picked": True})
        self.move.picking_id.button_validate()
        self.assertEqual(self.order_line.qty_received, 6)
        self.assertFalse(self.line.import_awaiting_receipt)
        # 5 of the document against 6 received and not invoiced
        self.assertEqual(self.line.import_qty_difference, -1.0)
        self.assertTrue(self.line.import_divergent)
