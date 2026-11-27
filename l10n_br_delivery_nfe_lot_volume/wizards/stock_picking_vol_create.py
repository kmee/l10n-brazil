# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, api, fields, models


class StockPickingVolCreate(models.TransientModel):
    _name = "stock.picking.vol.create"
    _description = "Create Volume from Move Lines"

    picking_id = fields.Many2one(comodel_name="stock.picking", required=True)
    move_id = fields.Many2one(comodel_name="stock.move")
    quantity = fields.Char(string="Volumes Quantity", default="1")
    kind = fields.Char(default="Box", required=True)
    brand = fields.Char()
    number = fields.Char(string="Numbering", default="1")
    net_weight = fields.Float(string="Net Weight (kg)", digits=(16, 3))
    gross_weight = fields.Float(string="Gross Weight (kg)", digits=(16, 3))
    line_ids = fields.One2many(
        comodel_name="stock.picking.vol.line",
        inverse_name="create_wizard_id",
        string="Lots",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        picking = self.env["stock.picking"].browse(res.get("picking_id"))
        move = self.env["stock.move"].browse(res.get("move_id"))
        lines = picking.move_line_ids.filtered(lambda line: not line.volume_id)
        res["line_ids"] = [
            Command.create({"move_line_id": line.id, "selected": line.move_id == move})
            for line in lines
        ]
        return res

    def action_create_volume(self):
        self.ensure_one()
        lines = self.line_ids.filtered("selected").move_line_id
        volume = self.env["stock.picking.vol"].create(
            {
                "picking_id": self.picking_id.id,
                "nfe40_qVol": self.quantity,
                "nfe40_esp": self.kind,
                "nfe40_marca": self.brand,
                "nfe40_nVol": self.number,
                "nfe40_pesoL": self.net_weight,
                "nfe40_pesoB": self.gross_weight,
                "move_line_ids": [Command.set(lines.ids)],
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.picking.vol",
            "res_id": volume.id,
            "view_mode": "form",
        }
