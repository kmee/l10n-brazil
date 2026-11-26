# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date
from unittest import mock

from odoo.addons.l10n_br_fiscal_edi.tools import EdiLot

from .common import StockEdiCase


class TestReceiptSameProduct(StockEdiCase):
    """The receipt created from a document with two lines of the same product."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.other = cls.env["product.product"].create(
            {"name": "Other stocked product", "type": "consu", "is_storable": True}
        )
        cls.third = cls.env["product.product"].create(
            {"name": "Third stocked product", "type": "consu", "is_storable": True}
        )

    def _note(self, products, quantities=None, prices=None):
        """A document without order, a line for each product, all marked as
        without order and with no receipt yet."""
        quantities = quantities or [1.0 + index for index in range(len(products))]
        prices = prices or [10.0] * len(products)
        document = self._imported_document(
            lines=[
                {"quantity": quantity, "price_unit": price}
                for quantity, price in zip(quantities, prices, strict=True)
            ]
        )
        for line, product in zip(document.fiscal_line_ids, products, strict=True):
            line._apply_import_depara(
                product=product, uom=self.unit, fiscal_operation=self.operation
            )
        self._rows(fiscal_document_id=document.id).action_no_order()
        return document, self._rows(fiscal_document_id=document.id)

    def test_two_lines_of_the_same_product_each_keep_a_move(self):
        document, note = self._note(
            [self.product, self.product, self.other, self.third],
            quantities=[3.0, 2.0, 5.0, 7.0],
        )

        action = note.action_create_receipt()

        picking = self.env["stock.picking"].browse(action["res_id"])
        lines = document.fiscal_line_ids
        self.assertEqual(picking.state, "assigned")
        self.assertEqual(len(picking.move_ids), 4)
        self.assertEqual(lines.import_stock_move_id, picking.move_ids)
        for line in lines:
            move = line.import_stock_move_id
            self.assertEqual(move.product_id, line.product_id)
            self.assertEqual(move.product_uom_qty, line.quantity)
        self.assertEqual(sum(picking.move_ids.mapped("product_uom_qty")), 17.0)
        same = picking.move_ids.filtered(lambda move: move.product_id == self.product)
        self.assertEqual(sum(same.mapped("product_uom_qty")), 5.0)
        self.assertTrue(document.action_generate_invoice())

    def test_validating_the_receipt_does_not_make_the_lines_divergent(self):
        document, note = self._note([self.product, self.product], [3.0, 2.0])
        action = note.action_create_receipt()
        picking = self.env["stock.picking"].browse(action["res_id"])

        picking.move_ids.write({"picked": True})
        picking._action_done()

        self.assertEqual(picking.state, "done")
        lines = document.fiscal_line_ids
        self.assertFalse(any(lines.mapped("import_divergent")))
        self.assertFalse(any(lines.mapped("import_awaiting_receipt")))
        self.assertEqual(
            self.env["stock.quant"]._get_available_quantity(
                self.product, picking.location_dest_id
            ),
            5.0,
        )
        self.assertTrue(document.action_generate_invoice())

    def test_different_prices_of_the_same_product_keep_their_own_cost(self):
        document, note = self._note(
            [self.product, self.product], [3.0, 2.0], prices=[10.0, 12.0]
        )

        note.action_create_receipt()

        costs = {
            line.quantity: line.import_stock_move_id.price_unit
            for line in document.fiscal_line_ids
        }
        self.assertEqual(costs, {3.0: 10.0, 2.0: 12.0})

    def test_all_products_distinct_stay_one_move_each(self):
        document, note = self._note([self.product, self.other, self.third])

        action = note.action_create_receipt()

        picking = self.env["stock.picking"].browse(action["res_id"])
        self.assertEqual(len(picking.move_ids), 3)
        self.assertEqual(
            document.fiscal_line_ids.import_stock_move_id, picking.move_ids
        )
        for line in document.fiscal_line_ids:
            self.assertEqual(line.import_stock_move_id.product_id, line.product_id)

    def test_the_lots_of_each_line_of_the_same_product_are_proposed(self):
        self.product.tracking = "lot"
        document, note = self._note([self.product, self.product], [3.0, 2.0])
        first, second = document.fiscal_line_ids
        declared = {
            first.id: [EdiLot("L-A", 3.0, None, date(2027, 1, 10))],
            second.id: [EdiLot("L-B", 2.0, None, date(2027, 6, 30))],
        }
        patcher = mock.patch.object(
            type(first),
            "_edi_get_lots",
            autospec=True,
            side_effect=lambda line: declared[line.id],
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        action = note.action_create_receipt()
        picking = self.env["stock.picking"].browse(action["res_id"])
        self.assertTrue(picking.show_propose_lots_from_import)

        picking.action_propose_lots_from_import()

        self.assertEqual(first.import_stock_move_id.move_line_ids.lot_name, "L-A")
        self.assertEqual(second.import_stock_move_id.move_line_ids.lot_name, "L-B")
        self.assertEqual(sorted(picking.move_line_ids.mapped("quantity")), [2.0, 3.0])
