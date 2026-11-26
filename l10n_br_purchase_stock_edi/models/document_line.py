# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class FiscalDocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    import_stock_move_id = fields.Many2one(
        comodel_name="stock.move",
        string="Receipt Move (origin)",
        copy=False,
        index=True,
        ondelete="set null",
        domain="[('picking_type_id.code', '=', 'incoming'),"
        " ('state', '!=', 'cancel'),"
        " ('purchase_line_id', '=', import_purchase_line_id)]",
        help="Receipt move this imported document line corresponds to. It is "
        "filled when the origin is decided and the order line has a single "
        "candidate (the received and not yet invoiced one first, else the "
        "only one still to come), or chosen on the line.",
    )

    import_ordered_qty = fields.Float(
        string="Order Qty",
        compute="_compute_import_comparison",
        digits="Product Unit of Measure",
        help="Quantity of the order line, in the unit of this line.",
    )
    import_received_qty = fields.Float(
        string="Order Received Qty",
        compute="_compute_import_comparison",
        digits="Product Unit of Measure",
        help="Quantity received for the order line, in the unit of this line.",
    )
    import_order_price_unit = fields.Float(
        string="Order Price",
        compute="_compute_import_comparison",
        digits="Product Price",
        help="Unit price of the order line, in the unit of this line.",
    )
    import_qty_difference = fields.Float(
        string="Qty vs Receipt",
        compute="_compute_import_comparison",
        digits="Product Unit of Measure",
        help="Quantity of the document for the order line minus the received "
        "quantity that the bills did not take yet.",
    )
    import_price_difference = fields.Float(
        string="Price vs Order",
        compute="_compute_import_comparison",
        digits="Product Price",
        help="Unit price of the line minus the unit price of the order line.",
    )
    import_awaiting_receipt = fields.Boolean(
        string="Awaiting Receipt",
        compute="_compute_import_comparison",
        search="_search_import_awaiting_receipt",
        help="The line is matched to an order line of a product that goes to the "
        "stock and nothing was received yet. It only informs: it is not a "
        "divergence.",
    )
    import_divergent = fields.Boolean(
        string="Divergent Line",
        compute="_compute_import_comparison",
        search="_search_import_divergent",
        help="The line differs from the order and the receipt by more than the "
        "tolerances of the company. It only warns: nothing is blocked.",
    )

    @api.depends(
        "import_purchase_line_id.product_qty",
        "import_purchase_line_id.product_uom",
        "import_purchase_line_id.qty_received",
        "import_purchase_line_id.qty_invoiced",
        "import_purchase_line_id.price_unit",
        "document_id.fiscal_line_ids.import_purchase_line_id",
        "document_id.fiscal_line_ids.quantity",
        "quantity",
        "price_unit",
        "uom_id",
        "company_id.purchase_price_tolerance",
        "company_id.purchase_quantity_tolerance",
    )
    def _compute_import_comparison(self):
        for line in self:
            values = {
                "ordered": 0.0,
                "received": 0.0,
                "price": 0.0,
                "qty_difference": 0.0,
                "price_difference": 0.0,
                "divergent": False,
                "awaiting": False,
            }
            order_line = line.import_purchase_line_id
            if order_line and line._is_imported():
                together = line.document_id.fiscal_line_ids.filtered(
                    lambda other, order_line=order_line: (
                        other.import_purchase_line_id == order_line
                    )
                )
                quantity = sum(
                    other.uom_id._compute_quantity(
                        other.quantity, line.uom_id, raise_if_failure=False
                    )
                    if other.uom_id and line.uom_id
                    else other.quantity
                    for other in together
                )
                values = order_line._import_compare(
                    quantity,
                    line.uom_id,
                    line.price_unit,
                    line.company_id.currency_id,
                    line.document_id.document_date or fields.Date.context_today(line),
                    line.document_id.sudo().move_ids,
                )
            line.import_ordered_qty = values["ordered"]
            line.import_received_qty = values["received"]
            line.import_order_price_unit = values["price"]
            line.import_qty_difference = values["qty_difference"]
            line.import_price_difference = values["price_difference"]
            line.import_divergent = values["divergent"]
            line.import_awaiting_receipt = values["awaiting"]

    def action_open_import_origin(self):
        """The receipt of the line comes first (it is what arrives at the
        warehouse); without one, the order of the base module."""
        self.ensure_one()
        picking = self.sudo().import_stock_move_id.picking_id
        if not picking:
            return super().action_open_import_origin()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking",
            "res_id": picking.id,
            "views": [(False, "form")],
            "target": "current",
        }

    def write(self, vals):
        if "import_stock_move_id" in vals and "import_purchase_line_id" not in vals:
            move = self.env["stock.move"].browse(vals["import_stock_move_id"])
            if move.purchase_line_id:
                vals = dict(vals, import_purchase_line_id=move.purchase_line_id.id)
        elif "import_purchase_line_id" in vals and "import_stock_move_id" not in vals:
            # the receipt follows the order line: its only candidate, if any
            vals = dict(vals, import_stock_move_id=self._import_single_receipt(vals))
        return super().write(vals)

    @api.model
    def _import_single_receipt(self, vals):
        order_line = self.env["purchase.order.line"].browse(
            vals["import_purchase_line_id"]
        )
        moves = order_line._import_receipt_moves() if order_line else order_line
        return moves.id if len(moves) == 1 else False

    def _imported_open_lines(self):
        lines = self.sudo().search(
            [
                ("import_purchase_line_id", "!=", False),
                ("document_id.imported_document", "=", True),
            ]
        )
        return lines.filtered(lambda line: line.document_id._import_is_open())

    @api.model
    def _search_import_awaiting_receipt(self, operator, value):
        """Same reading of the divergence: the receipts move after the document
        is typed, so nothing is stored."""
        if operator not in ("=", "!="):
            raise NotImplementedError("Only = and != are supported.")
        awaiting = self._imported_open_lines().filtered("import_awaiting_receipt")
        if (operator == "=") == bool(value):
            return [("id", "in", awaiting.ids)]
        return [("id", "not in", awaiting.ids)]

    @api.model
    def _search_import_divergent(self, operator, value):
        """Not stored (the receipts move after the document is typed): the
        search looks at the lines that point to an order line of a document
        still open."""
        if operator not in ("=", "!="):
            raise NotImplementedError("Only = and != are supported.")
        divergent = self._imported_open_lines().filtered("import_divergent")
        if (operator == "=") == bool(value):
            return [("id", "in", divergent.ids)]
        return [("id", "not in", divergent.ids)]
