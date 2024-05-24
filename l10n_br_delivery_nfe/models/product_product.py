# Copyright (C) 2024 Diego Paradeda - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    product_nfe40_esp = fields.Char(string="Espécie dos volumes transportados")

    product_nfe40_marca = fields.Char(string="Marca dos volumes transportados")

    # Manter compatibilidade com módulo: product_net_weight
    net_weight = fields.Float(
        string="Net Weight",
    )
