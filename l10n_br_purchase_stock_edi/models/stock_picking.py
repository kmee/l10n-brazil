# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    show_propose_lots_from_import = fields.Boolean(
        compute="_compute_show_propose_lots_from_import",
        help="Technical: a receipt waiting for lots whose moves are the origin "
        "of imported document lines that declare lots.",
    )

    @api.depends("state", "move_ids")
    def _compute_show_propose_lots_from_import(self):
        for picking in self:
            picking.show_propose_lots_from_import = bool(
                picking.state not in ("done", "cancel")
                and any(move._import_declared_lots() for move in picking.move_ids)
            )

    def action_propose_lots_from_import(self):
        """Propose, on the receipt, the lots and expiry dates the document that is
        the origin of its moves declared. The operator reviews and validates."""
        self.ensure_one()
        reasons = []
        proposed = 0
        for move in self.move_ids:
            if not move._import_declared_lots():
                continue
            reason = move._propose_lots_from_import()
            if reason:
                reasons.append(reason)
            else:
                proposed += 1
        message = _("%s move(s) received the lots of the document.", proposed)
        if reasons:
            message += "\n" + "\n".join(reasons)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Lots of the document"),
                "message": message,
                "type": "success" if proposed else "warning",
                "sticky": bool(reasons),
            },
        }
