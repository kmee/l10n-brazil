# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class ProductProduct(models.Model):

    _inherit = "product.product"

    def availability_text_get(self):
        self.ensure_one()
        availability = {r.id: [r.free_qty, r.uom_id.name] for r in self}
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        availability_text = "({:.{}f} {})".format(
            self.free_qty, precision, self.uom_id.name
        )
        return availability_text
