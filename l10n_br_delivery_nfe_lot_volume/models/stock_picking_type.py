# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockPickingType(models.Model):
    _inherit = "stock.picking.type"

    require_lot_volume = fields.Boolean(
        string="Require Volume for Each Lot",
        help="When checked, a transfer of this operation type can only be "
        "validated when every move line with a lot is inside a volume.",
    )
