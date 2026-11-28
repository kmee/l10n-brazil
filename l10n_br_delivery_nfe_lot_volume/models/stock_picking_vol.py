# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockPickingVol(models.Model):
    _inherit = "stock.picking.vol"

    name = fields.Char(compute="_compute_name", store=True)

    move_line_ids = fields.One2many(
        comodel_name="stock.move.line",
        inverse_name="volume_id",
        string="Lots",
    )

    @api.depends("nfe40_esp", "nfe40_marca", "nfe40_nVol")
    def _compute_name(self):
        for vol in self:
            vol.name = "/".join(
                (vol.nfe40_esp or "", vol.nfe40_marca or "", vol.nfe40_nVol or "")
            )

    @api.model_create_multi
    def create(self, vals_list):
        vols = super().create(vals_list)
        for picking in vols.picking_id:
            picking.write(
                {
                    "has_vol": True,
                    "number_of_volumes": sum(
                        float(qty or 0) for qty in picking.vol_ids.mapped("nfe40_qVol")
                    ),
                }
            )
        return vols

    def action_open_add_lines_wizard(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "l10n_br_delivery_nfe_lot_volume.action_stock_picking_vol_add"
        )
        action["context"] = {
            "default_picking_id": self.picking_id.id,
            "default_volume_id": self.id,
        }
        return action
