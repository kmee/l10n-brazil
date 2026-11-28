# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, api, fields, models


class StockPickingVolAdd(models.TransientModel):
    _name = "stock.picking.vol.add"
    _description = "Add Move Lines to a Volume"

    picking_id = fields.Many2one(comodel_name="stock.picking", required=True)
    volume_id = fields.Many2one(
        comodel_name="stock.picking.vol",
        required=True,
        domain="[('picking_id', '=', picking_id)]",
    )
    line_ids = fields.One2many(
        comodel_name="stock.picking.vol.line",
        inverse_name="add_wizard_id",
        string="Lots",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        picking = self.env["stock.picking"].browse(res.get("picking_id"))
        lines = picking.move_line_ids.filtered(lambda line: not line.volume_id)
        res["line_ids"] = [Command.create({"move_line_id": line.id}) for line in lines]
        return res

    def action_add_to_volume(self):
        self.ensure_one()
        lines = self.line_ids.filtered("selected").move_line_id
        self.volume_id.write(
            {"move_line_ids": [Command.link(id_) for id_ in lines.ids]}
        )
