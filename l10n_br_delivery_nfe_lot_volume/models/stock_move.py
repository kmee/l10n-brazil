# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockMove(models.Model):
    _inherit = "stock.move"

    volume_ids = fields.Many2many(
        comodel_name="stock.picking.vol",
        relation="stock_move_picking_vol_rel",
        column1="move_id",
        column2="vol_id",
        string="Volumes",
        compute="_compute_volume_ids",
        store=True,
    )

    @api.depends("move_line_ids.volume_id")
    def _compute_volume_ids(self):
        for move in self:
            move.volume_ids = move.move_line_ids.volume_id

    def action_open_create_volume_wizard(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "l10n_br_delivery_nfe_lot_volume.action_stock_picking_vol_create"
        )
        action["context"] = {
            "default_picking_id": self.picking_id.id,
            "default_move_id": self.id,
        }
        return action
