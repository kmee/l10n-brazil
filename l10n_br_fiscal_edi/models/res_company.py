# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    import_product_categ_id = fields.Many2one(
        comodel_name="product.category",
        string="Default Category of Products Created by the Import",
        help="Category given to the products that the action 'Create Missing "
        "Products' of an imported document creates. Empty: the default category "
        "of the products.",
    )
