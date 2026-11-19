# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date, datetime

from odoo import Command

from .common import StockImportCase


class TestLots(StockImportCase):
    def _lots(self, quantity=4):
        """A tracked product ordered, and a document line with two lots."""
        self.product.tracking = "lot"
        self.order = self._order(quantity=quantity)
        self.move = self._moves(self.order)
        self.line.write({"quantity": quantity, "uom_id": self.unit.id})
        half = quantity / 2
        self.line.write(
            {
                "nfe40_rastro": [
                    Command.create(
                        {
                            "nfe40_nLote": "L-A",
                            "nfe40_qLote": half,
                            "nfe40_dVal": date(2027, 1, 10),
                        }
                    ),
                    Command.create(
                        {
                            "nfe40_nLote": "L-B",
                            "nfe40_qLote": half,
                            "nfe40_dVal": date(2027, 6, 30),
                        }
                    ),
                ]
            }
        )
        self._resolve_product()
        self.assertEqual(self.line.import_stock_move_id, self.move)
        return half

    def test_the_lots_of_the_nfe_are_proposed_not_validated(self):
        half = self._lots()
        picking = self.order.picking_ids
        self.assertTrue(picking.show_propose_lots_from_nfe)

        picking.action_propose_lots_from_nfe()

        lines = self.move.move_line_ids
        self.assertEqual(sorted(lines.mapped("lot_name")), ["L-A", "L-B"])
        self.assertEqual(sorted(lines.mapped("qty_done")), [half, half])
        if "expiration_date" in lines._fields:
            line_a = lines.filtered(lambda line: line.lot_name == "L-A")
            self.assertEqual(line_a.expiration_date, datetime(2027, 1, 10))
        # the receipt creates the lots on validation: nothing created now
        self.assertFalse(self.env["stock.lot"].search([("name", "in", ["L-A", "L-B"])]))
        self.assertEqual((picking.state, self.move.state), ("assigned", "assigned"))

    def test_an_existing_lot_is_used_by_its_id(self):
        self._lots()
        lot = self.env["stock.lot"].create(
            {
                "name": "L-A",
                "product_id": self.product.id,
                "company_id": self.move.company_id.id,
            }
        )

        self.move._propose_lots_from_nfe()

        lines = self.move.move_line_ids
        self.assertEqual(lines.filtered("lot_id").lot_id, lot)
        self.assertEqual(lines.filtered("lot_name").mapped("lot_name"), ["L-B"])

    def test_a_type_that_does_not_create_lots_gets_the_lot_now(self):
        self._lots()
        self.move.picking_type_id.use_create_lots = False
        self.move.picking_type_id.use_existing_lots = True

        self.move._propose_lots_from_nfe()

        self.assertEqual(
            sorted(self.move.move_line_ids.mapped("lot_id.name")), ["L-A", "L-B"]
        )
        self.assertEqual(self.order.picking_ids.state, "assigned")

    def test_a_product_without_lot_tracking_is_left_alone(self):
        self._lots()
        self.product.tracking = "none"
        before = self.move.move_line_ids

        self.assertTrue(self.move._propose_lots_from_nfe())

        self.assertEqual(self.move.move_line_ids, before)
        self.assertFalse(self.move.move_line_ids.lot_id)

    def test_a_receipt_already_filled_is_not_overwritten(self):
        self._lots()
        self.move.move_line_ids.write({"qty_done": 1.0})

        self.assertTrue(self.move._propose_lots_from_nfe())

        self.assertFalse(self.move.move_line_ids.lot_id)
        self.assertFalse(self.move.move_line_ids.lot_name)

    def test_open_receipt_proposes_the_lots_too(self):
        self._lots()

        self._rows(fiscal_document_id=self.document.id).action_open_receipt()

        self.assertEqual(
            sorted(self.move.move_line_ids.mapped("lot_name")), ["L-A", "L-B"]
        )
