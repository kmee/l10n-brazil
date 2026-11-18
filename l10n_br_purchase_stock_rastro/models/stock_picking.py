# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    show_propose_lots_from_nfe = fields.Boolean(
        compute="_compute_show_propose_lots_from_nfe",
        help="Technical: a receipt waiting for lots whose moves are the origin "
        "of imported NF-e lines that carry the lot group.",
    )

    @api.depends("state", "move_ids")
    def _compute_show_propose_lots_from_nfe(self):
        for picking in self:
            picking.show_propose_lots_from_nfe = bool(
                picking.state not in ("done", "cancel")
                and any(move._nfe_rastro_lines() for move in picking.move_ids)
            )

    def action_propose_lots_from_nfe(self):
        """Propose, on the receipt, the lots and expiry dates of the NF-e that
        is the origin of its moves. The operator reviews and validates."""
        self.ensure_one()
        reasons = []
        proposed = 0
        for move in self.move_ids:
            if not move._nfe_rastro_lines():
                continue
            reason = move._propose_lots_from_nfe()
            if reason:
                reasons.append(reason)
            else:
                proposed += 1
        message = _("%s move(s) received the lots of the NF-e.", proposed)
        if reasons:
            message += "\n" + "\n".join(reasons)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Lots of the NF-e"),
                "message": message,
                "type": "success" if proposed else "warning",
                "sticky": bool(reasons),
            },
        }
