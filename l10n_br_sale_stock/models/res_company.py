# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    sale_picking_by_fiscal_operation = fields.Boolean(
        string="One Picking per Fiscal Operation",
        help="Create one delivery for each fiscal operation of the sale order"
        " lines. Otherwise all the lines go to a single delivery, with the"
        " fiscal operation of the sale order.",
    )
