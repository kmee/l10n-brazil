# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date, datetime

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProposeLots(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.order = cls.env.ref("l10n_br_purchase.lp_po_only_products")
        cls.operation = cls.env.ref("l10n_br_fiscal.fo_compras")
        cls.operation_line = cls.env.ref("l10n_br_fiscal.fo_compras_compras")
        for line in cls.order.order_line:
            line.product_id.purchase_method = "purchase"
        cls.tracked, cls.untracked = cls.order.order_line.mapped("product_id")[:2]
        cls.tracked.tracking = "lot"
        cls.tracked.use_expiration_date = True
        cls.untracked.tracking = "none"
        cls.order.button_confirm()
        cls.picking = cls.order.picking_ids
        cls.document = cls.env["l10n_br_fiscal.document"].create(
            {
                "company_id": cls.order.company_id.id,
                "fiscal_operation_id": cls.operation.id,
                "fiscal_operation_type": "in",
                "document_type_id": cls.env.ref("l10n_br_fiscal.document_55").id,
                "document_number": "8801",
                "document_serie": "1",
                "issuer": "partner",
                "partner_id": cls.order.partner_id.id,
                "imported_document": True,
            }
        )

    def _line(self, product, rastro, with_move=True):
        move = self.picking.move_ids.filtered(lambda mv: mv.product_id == product)
        order_line = self.order.order_line.filtered(lambda ol: ol.product_id == product)
        return self.env["l10n_br_fiscal.document.line"].create(
            {
                "document_id": self.document.id,
                "name": product.name,
                "product_id": product.id,
                "quantity": order_line.product_qty,
                "price_unit": order_line.price_unit,
                "fiscal_operation_id": self.operation.id,
                "fiscal_operation_line_id": self.operation_line.id,
                "fiscal_operation_type": "in",
                "import_purchase_line_id": order_line.id,
                "import_stock_move_id": move.id if with_move else False,
                "nfe40_rastro": [Command.create(vals) for vals in rastro],
            }
        )

    def _two_lots(self, move):
        half = move.product_uom_qty / 2
        return half, [
            {
                "nfe40_nLote": "L-A",
                "nfe40_qLote": half,
                "nfe40_dFab": date(2026, 1, 10),
                "nfe40_dVal": date(2027, 1, 10),
            },
            {
                "nfe40_nLote": "L-B",
                "nfe40_qLote": half,
                "nfe40_dVal": date(2027, 6, 30),
            },
        ]

    def test_the_lots_of_the_nfe_are_proposed_not_validated(self):
        move = self.picking.move_ids.filtered(lambda mv: mv.product_id == self.tracked)
        half, rastro = self._two_lots(move)
        self._line(self.tracked, rastro)
        self.assertEqual(self.picking.state, "assigned")
        self.assertTrue(self.picking.show_propose_lots_from_nfe)
        self.picking.action_propose_lots_from_nfe()
        lines = move.move_line_ids
        self.assertEqual(sorted(lines.mapped("lot_name")), ["L-A", "L-B"])
        self.assertEqual(sorted(lines.mapped("qty_done")), [half, half])
        line_a = lines.filtered(lambda line: line.lot_name == "L-A")
        self.assertEqual(line_a.expiration_date, datetime(2027, 1, 10))
        # the receipt creates the lots on validation: nothing created now
        self.assertFalse(
            self.env["stock.lot"].search_count([("name", "in", ["L-A", "L-B"])])
        )
        # the receipt stays Ready, it does not go back to Waiting
        self.assertEqual(self.picking.state, "assigned")
        self.assertEqual(move.state, "assigned")

    def test_an_existing_lot_is_used_by_its_id(self):
        move = self.picking.move_ids.filtered(lambda mv: mv.product_id == self.tracked)
        lot = self.env["stock.lot"].create(
            {
                "name": "L-A",
                "product_id": self.tracked.id,
                "company_id": move.company_id.id,
            }
        )
        half, rastro = self._two_lots(move)
        self._line(self.tracked, rastro)
        move._propose_lots_from_nfe()
        lines = move.move_line_ids
        self.assertEqual(lines.filtered(lambda line: line.lot_id).lot_id, lot)
        self.assertEqual(lines.filtered("lot_name").mapped("lot_name"), ["L-B"])

    def test_a_type_that_does_not_create_lots_gets_the_lot_now(self):
        move = self.picking.move_ids.filtered(lambda mv: mv.product_id == self.tracked)
        move.picking_type_id.use_create_lots = False
        move.picking_type_id.use_existing_lots = True
        half, rastro = self._two_lots(move)
        self._line(self.tracked, rastro)
        move._propose_lots_from_nfe()
        self.assertEqual(
            sorted(move.move_line_ids.mapped("lot_id.name")), ["L-A", "L-B"]
        )
        self.assertEqual(self.picking.state, "assigned")

    def test_the_receipt_is_found_by_the_order_line_when_no_move_is_recorded(self):
        move = self.picking.move_ids.filtered(lambda mv: mv.product_id == self.tracked)
        half, rastro = self._two_lots(move)
        self._line(self.tracked, rastro, with_move=False)
        self.assertTrue(self.picking.show_propose_lots_from_nfe)
        self.picking.action_propose_lots_from_nfe()
        self.assertEqual(sorted(move.move_line_ids.mapped("lot_name")), ["L-A", "L-B"])

    def test_a_product_without_lot_tracking_is_left_alone(self):
        move = self.picking.move_ids.filtered(
            lambda mv: mv.product_id == self.untracked
        )
        self._line(self.untracked, [{"nfe40_nLote": "L-X", "nfe40_qLote": 1.0}])
        before = move.move_line_ids
        reason = move._propose_lots_from_nfe()
        self.assertTrue(reason)
        self.assertEqual(move.move_line_ids, before)
        self.assertFalse(move.move_line_ids.lot_id)

    def test_a_receipt_already_filled_is_not_overwritten(self):
        move = self.picking.move_ids.filtered(lambda mv: mv.product_id == self.tracked)
        self._line(self.tracked, [{"nfe40_nLote": "L-N", "nfe40_qLote": 1.0}])
        move.move_line_ids.write({"qty_done": 1.0})
        self.assertTrue(move._propose_lots_from_nfe())
        self.assertFalse(move.move_line_ids.lot_id)
