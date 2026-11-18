# Copyright 2026 KMEE - Luis Felipe Mileo <mileo@kmee.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestImportOriginMove(TransactionCase):
    """With stock, the origin of an imported line also points to the pending
    receipt move of the order line."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.order = cls.env.ref("l10n_br_purchase.lp_po_only_products")
        cls.operation = cls.env.ref("l10n_br_fiscal.fo_compras")
        cls.operation_line = cls.env.ref("l10n_br_fiscal.fo_compras_compras")
        for line in cls.order.order_line:
            line.product_id.purchase_method = "purchase"
        cls.order.button_confirm()

    def _document(self, order_line):
        order = self.order
        document = self.env["l10n_br_fiscal.document"].create(
            {
                "company_id": order.company_id.id,
                "fiscal_operation_id": self.operation.id,
                "fiscal_operation_type": "in",
                "document_type_id": self.env.ref("l10n_br_fiscal.document_55").id,
                "document_number": "7710",
                "document_serie": "1",
                "issuer": "partner",
                "partner_id": order.partner_id.id,
                "imported_document": True,
            }
        )
        self.env["l10n_br_fiscal.document.line"].create(
            {
                "document_id": document.id,
                "name": order_line.name,
                "product_id": order_line.product_id.id,
                "quantity": order_line.product_qty,
                "price_unit": order_line.price_unit,
                "fiscal_operation_id": self.operation.id,
                "fiscal_operation_line_id": self.operation_line.id,
                "fiscal_operation_type": "in",
                "partner_order": order.name,
                "partner_order_line": "1",
            }
        )
        return document

    def test_the_pending_receipt_move_is_suggested(self):
        order_line = self.order.order_line[0]
        moves = order_line.move_ids.filtered(lambda move: move.state != "cancel")
        self.assertEqual(len(moves), 1)
        document = self._document(order_line)
        document._init_import_states()
        line = document.fiscal_line_ids
        self.assertEqual(line.import_purchase_line_id, order_line)
        self.assertEqual(line.import_stock_move_id, moves)

    def test_picking_the_move_sets_the_order_line(self):
        order_line = self.order.order_line[1]
        move = order_line.move_ids.filtered(lambda mv: mv.state != "cancel")
        document = self._document(self.order.order_line[0])
        line = document.fiscal_line_ids
        line.import_stock_move_id = move
        self.assertEqual(line.import_purchase_line_id, order_line)
        self.assertEqual(line.import_origin_state, "resolved")
