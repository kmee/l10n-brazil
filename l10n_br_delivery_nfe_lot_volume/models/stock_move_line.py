# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    volume_id = fields.Many2one(
        comodel_name="stock.picking.vol",
        string="Volume",
        ondelete="set null",
    )

    @api.depends("lot_id", "product_id")
    def _compute_display_name(self):
        for line in self:
            if line.lot_id:
                line.display_name = (
                    f"{line.product_id.display_name} [{line.lot_id.name}]"
                )
            else:
                line.display_name = line.product_id.display_name

    def action_remove_from_volume(self):
        self.volume_id = False
