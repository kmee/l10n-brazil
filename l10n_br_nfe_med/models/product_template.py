# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    nfe40_med = fields.Many2one(
        comodel_name="nfe.40.med",
        string="Medicine (ANVISA)",
        help="ANVISA code and maximum consumer price (PMC) reported in the "
        "medicine group of the NF-e items of this product.",
    )
