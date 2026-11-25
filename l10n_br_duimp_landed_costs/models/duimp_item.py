# Copyright 2026 KMEE INFORMATICA LTDA - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.tools.float_utils import float_compare


class L10nBrDuimpItem(models.Model):
    _inherit = "l10n_br_duimp.item"

    move_ids = fields.One2many(
        comodel_name="stock.move",
        inverse_name="duimp_item_id",
        string="Receipt Moves",
        readonly=True,
    )

    received_qty = fields.Float(
        string="Linked Quantity",
        compute="_compute_received_qty",
        digits="Product Unit of Measure",
        help="Quantity of the receipts linked to this item, in its unit of measure.",
    )

    receipt_pending = fields.Boolean(
        compute="_compute_received_qty",
        help="The linked receipts do not cover the item quantity yet.",
    )

    @api.depends("move_ids.product_qty", "move_ids.state", "quantity")
    def _compute_received_qty(self):
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        for item in self:
            moves = item.move_ids.filtered(lambda move: move.state != "cancel")
            item.received_qty = sum(move._get_duimp_item_qty() for move in moves)
            item.receipt_pending = (
                float_compare(
                    item.received_qty, item.quantity, precision_digits=precision
                )
                < 0
            )
