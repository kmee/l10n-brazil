# Copyright (C) 2022  Renan Hiroki Bastos - Kmee
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import fields, models


class SupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    partner_uom = fields.Many2one(
        "uom.uom",
        "Partner Unit of Measure",
        required="True",
        help="This comes from the last imported document.",
    )

    def create(self, vals):
        res = super(SupplierInfo, self).create(vals)
        if not res.partner_uom:
            res.partner_uom = res.product_tmpl_id.uom_id
        return res
