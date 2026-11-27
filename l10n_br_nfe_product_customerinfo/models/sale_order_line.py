# Copyright 2026 KMEE (https://www.kmee.com.br)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    @api.onchange("product_id")
    def _onchange_partner_product(self):
        for line in self:
            line.update(
                line._get_partner_product_vals(
                    line.product_id, line.order_id.partner_id
                )
                or {"partner_product_code": False, "partner_product_name": False}
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                vals.get("product_id")
                and vals.get("order_id")
                and not vals.get("partner_product_code")
                and not vals.get("partner_product_name")
            ):
                order = self.env["sale.order"].browse(vals["order_id"])
                product = self.env["product.product"].browse(vals["product_id"])
                vals.update(self._get_partner_product_vals(product, order.partner_id))
        return super().create(vals_list)
