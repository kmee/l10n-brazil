# Copyright 2026 KMEE INFORMATICA LTDA - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models

from .stock_landed_cost import BY_CUSTOMS_VALUE, SPLIT_METHOD_CUSTOMS_VALUE


class ProductTemplate(models.Model):
    _inherit = "product.template"

    split_method_landed_cost = fields.Selection(
        selection_add=SPLIT_METHOD_CUSTOMS_VALUE,
        ondelete={BY_CUSTOMS_VALUE: "set null"},
    )
