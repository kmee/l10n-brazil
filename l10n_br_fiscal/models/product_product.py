# Copyright (C) 2021  Renato Lima - Akretion <renato.lima@akretion.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import models, fields


class ProductProduct(models.Model):
    _name = "product.product"
    _inherit = ["product.product", "l10n_br_fiscal.product.mixin"]

    icms_regulation_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.icms.regulation",
        string="Tax Regulation",
        related="product_tmpl_id.icms_regulation_id",
        readonly=False,
    )
