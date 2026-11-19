# Copyright 2026 KMEE - Luis Felipe Mileo <mileo@kmee.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class FiscalDocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    import_stock_move_id = fields.Many2one(
        comodel_name="stock.move",
        string="Receipt Move (origin)",
        copy=False,
        index=True,
        ondelete="set null",
        domain="[('purchase_line_id', '=', import_purchase_line_id),"
        " ('state', 'not in', ('done', 'cancel'))]",
        help="Pending receipt move of the purchase order line this imported "
        "document line corresponds to. Suggested when the order line has a "
        "single pending receipt move.",
    )

    def write(self, vals):
        if (
            "import_stock_move_id" in vals
            and "import_purchase_line_id" not in vals
            and vals["import_stock_move_id"]
        ):
            move = self.env["stock.move"].browse(vals["import_stock_move_id"])
            vals = dict(vals, import_purchase_line_id=move.purchase_line_id.id)
        elif "import_purchase_line_id" in vals and "import_stock_move_id" not in vals:
            # the receipt follows the order line: its only pending move, if
            # there is exactly one candidate (same rule as the suggestion)
            order_line = self.env["purchase.order.line"].browse(
                vals["import_purchase_line_id"]
            )
            moves = self._pending_moves_of(order_line)
            vals = dict(
                vals, import_stock_move_id=moves.id if len(moves) == 1 else False
            )
        return super().write(vals)

    @api.model
    def _pending_moves_of(self, order_line):
        return order_line.sudo().move_ids.filtered(
            lambda move: move.state not in ("done", "cancel")
        )

    def _pending_receipt_moves(self):
        self.ensure_one()
        return self._pending_moves_of(self.import_purchase_line_id)

    def _suggest_import_origin(self):
        result = super()._suggest_import_origin()
        for line in self:
            if not line.import_purchase_line_id or line.import_stock_move_id:
                continue
            moves = line._pending_receipt_moves()
            if len(moves) == 1:
                line.with_context(import_origin_suggestion=True).write(
                    {"import_stock_move_id": moves.id}
                )
        return result

    def _apply_import_match_source(self, source, trusted=False):
        result = super()._apply_import_match_source(source, trusted=trusted)
        if source.source_type == "stock_move":
            move = self.env["stock.move"].browse(-source.id).exists()
            if move and (
                trusted
                or not move.purchase_line_id
                or self._import_origin_has_balance(move.purchase_line_id)
            ):
                self.write(
                    {
                        "import_stock_move_id": move.id,
                        "import_purchase_line_id": move.purchase_line_id.id,
                        "import_origin_state": "resolved" if trusted else "suggested",
                    }
                )
        return result
