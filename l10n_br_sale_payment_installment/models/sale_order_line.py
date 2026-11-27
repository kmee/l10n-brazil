# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    installment_surcharge_value = fields.Monetary(
        copy=False,
        readonly=True,
        help="Share of the installment interest charged by the company that is "
        "part of the other costs of the line.",
    )

    def copy_data(self, default=None):
        """A copied order has no installments chosen yet: leave the interest out
        of the other costs it inherits."""
        data_list = super().copy_data(default=default)
        for line, data in zip(self, data_list, strict=True):
            if line.installment_surcharge_value and "other_value" in data:
                data["other_value"] -= line.installment_surcharge_value
        return data_list
