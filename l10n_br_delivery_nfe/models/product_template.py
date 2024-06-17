# Copyright (C) 2024 Diego Paradeda - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    product_nfe40_esp = fields.Char(
        string="Type of transported volumes",
        compute="_compute_nfe40_esp",
        inverse="_inverse_nfe40_esp",
        store=True,
    )

    @api.depends("product_variant_ids", "product_variant_ids.product_nfe40_esp")
    def _compute_nfe40_esp(self):
        unique_variants = self.filtered(
            lambda template: len(template.product_variant_ids) == 1
        )
        for template in unique_variants:
            template.product_nfe40_esp = template.product_variant_ids.product_nfe40_esp
        for template in self - unique_variants:
            template.product_nfe40_esp = ""

    def _inverse_nfe40_esp(self):
        for template in self:
            if len(template.product_variant_ids) == 1:
                template.product_variant_ids.product_nfe40_esp = (
                    template.product_nfe40_esp
                )
