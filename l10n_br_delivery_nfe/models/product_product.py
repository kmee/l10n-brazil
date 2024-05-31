# Copyright (C) 2024 Diego Paradeda - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    product_nfe40_esp = fields.Char(
        string="Type of transported volumes",
    )

    product_nfe40_marca = fields.Char(
        string="Brand of transported volumes",
    )
