# Copyright (C) 2024 Diego Paradeda - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import fields, models


class StockPickingLacres(models.Model):
    _name = "stock.picking.lacres"
    _description = "lacres"
    _inherit = "nfe.40.lacres"

    # The inherited field points to nfe.40.vol, but the seal is registered on
    # the picking volume.
    nfe40_lacres_vol_id = fields.Many2one(
        comodel_name="stock.picking.vol",
        ondelete="cascade",
        index=True,
    )
