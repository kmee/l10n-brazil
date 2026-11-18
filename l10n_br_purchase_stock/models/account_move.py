# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    purchase_divergent = fields.Boolean(
        string="Divergent",
        compute="_compute_purchase_divergent",
        search="_search_purchase_divergent",
        help="Some line of the bill differs from its purchase order line or "
        "receipt by more than the tolerances of the company. It only warns: "
        "nothing is blocked.",
    )

    @api.depends("invoice_line_ids.purchase_divergent")
    def _compute_purchase_divergent(self):
        for move in self:
            move.purchase_divergent = any(
                move.invoice_line_ids.mapped("purchase_divergent")
            )

    @api.model
    def _search_purchase_divergent(self, operator, value):
        """Not stored (the receipts move after the bill is typed), so the search
        compares the bill lines that are linked to an order line, which are the
        only ones that can diverge, and answers with their bills."""
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise NotImplementedError(
                "Only the operators = and != against True or False are supported."
            )
        lines = self.env["account.move.line"].search(
            [
                ("purchase_line_id", "!=", False),
                ("display_type", "=", "product"),
                ("move_id.move_type", "in", ("in_invoice", "in_refund")),
                ("move_id.state", "!=", "cancel"),
            ]
        )
        divergent_ids = lines.filtered("purchase_divergent").move_id.ids
        if (operator == "=") == value:
            return [("id", "in", divergent_ids)]
        return [("id", "not in", divergent_ids)]
