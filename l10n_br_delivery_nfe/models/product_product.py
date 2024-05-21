# Copyright (C) 2024 Diego Paradeda - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import fields, models


class ProductProduct(models.Model):
    _inherit = "product.product"

    volume_type = fields.Selection(
        string="Volume Type",
        # TODO: ADD DEFAULT METHOD + res.company field
        selection=[
            ("manual", "Criar Manualmente"),
            ("product_qty", "Qtd. de Produtos"),
        ],
    )

    product_nfe40_esp = fields.Char(string="Espécie dos volumes transportados")

    product_nfe40_marca = fields.Char(string="Marca dos volumes transportados")

    product_nfe40_pesoL = fields.Float(
        string="Peso L. (kg)",
    )

    product_nfe40_pesoB = fields.Float(
        string="Peso B. (kg)",
    )
