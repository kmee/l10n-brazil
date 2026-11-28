# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockPickingVolLine(models.TransientModel):
    _name = "stock.picking.vol.line"
    _description = "Move Line to Put in a Volume"

    create_wizard_id = fields.Many2one(
        comodel_name="stock.picking.vol.create", ondelete="cascade"
    )
    add_wizard_id = fields.Many2one(
        comodel_name="stock.picking.vol.add", ondelete="cascade"
    )
    move_line_id = fields.Many2one(
        comodel_name="stock.move.line", required=True, ondelete="cascade"
    )
    product_id = fields.Many2one(related="move_line_id.product_id")
    lot_id = fields.Many2one(related="move_line_id.lot_id")
    quantity = fields.Float(related="move_line_id.quantity")
    product_uom_id = fields.Many2one(related="move_line_id.product_uom_id")
    selected = fields.Boolean()
