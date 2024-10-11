# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockProductionLot(models.Model):
    _inherit = "stock.production.lot"

    # _stack_skip = ("nfe40_rastro_prod_id",)

    # nfe40_nLote = fields.Char(
    #     related="name",
    # )

    # nfe40_qLote = fields.Float(
    #     related="product_qty",
    # )

    # nfe40_dFab = fields.Date()

    # nfe40_dVal = fields.Date()

    nfe40_cAgreg = fields.Char(string="cAgreg")
