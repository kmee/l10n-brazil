# Copyright (C) 2024 Diego Paradeda - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    product_nfe40_esp = fields.Char(
        string="Type of transported volumes",
        related="product_variant_ids.product_nfe40_esp",
        readonly=False,
    )

    product_nfe40_marca = fields.Char(
        string="Brand of transported volumes",
        related="product_variant_ids.product_nfe40_marca",
        readonly=False,
    )
