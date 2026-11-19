# Copyright (C) 2022  Renan Hiroki Bastos - Kmee
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import fields, models


class SupplierInfo(models.Model):
    _inherit = "product.supplierinfo"

    partner_uom_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Partner Unit of Measure",
    )

    partner_uom_factor = fields.Float(string="Partner UOM Factor", default=1)

    partner_uom_code = fields.Char(
        string="Supplier Unit Code",
        help="Unit the supplier declared in the file the de-para was learned from "
        "(a box, a kilo). The factor of the de-para only holds for this unit: a "
        "note of the same product code in another unit does not inherit it.",
    )
