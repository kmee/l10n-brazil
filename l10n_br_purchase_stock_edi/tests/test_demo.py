# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged

KEY_LOTS = "35261011765432000100550010000030011300100010"


@tagged("post_install", "-at_install")
class TestDemo(TransactionCase):
    """The receipt of the demo order took the lots of the note and was validated."""

    def setUp(self):
        super().setUp()
        if not self.env.ref("l10n_br_purchase_stock_edi.demo_order_lot", False):
            self.skipTest("No demo data")

    def test_the_receipt_has_the_lots_of_the_note_and_is_done(self):
        order = self.env.ref("l10n_br_purchase_stock_edi.demo_order_lot")
        document = self.env["l10n_br_fiscal.document"].search(
            [("document_key", "=", KEY_LOTS)]
        )
        line = document.fiscal_line_ids

        self.assertEqual(line.import_origin_state, "resolved")
        self.assertEqual(line.import_purchase_line_id, order.order_line)
        picking = order.picking_ids
        self.assertEqual(picking.state, "done")
        lots = {
            move_line.lot_id.name: move_line.qty_done
            for move_line in picking.move_line_ids
        }
        self.assertEqual(lots, {"L-DEMO-01": 6.0, "L-DEMO-02": 4.0})
        self.assertEqual(order.order_line.qty_received, 10.0)
