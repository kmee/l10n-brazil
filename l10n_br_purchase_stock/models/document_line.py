# Copyright 2026 KMEE - Luis Felipe Mileo <mileo@kmee.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


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
        return super().write(vals)

    def _pending_receipt_moves(self):
        self.ensure_one()
        return self.import_purchase_line_id.move_ids.filtered(
            lambda move: move.state not in ("done", "cancel")
        )

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

    def _apply_import_match_source(self, source):
        result = super()._apply_import_match_source(source)
        if source.source_type == "stock_move":
            move = self.env["stock.move"].browse(-source.id).exists()
            if move:
                self.write(
                    {
                        "import_stock_move_id": move.id,
                        "import_purchase_line_id": move.purchase_line_id.id,
                        "import_origin_state": "suggested",
                    }
                )
        return result
