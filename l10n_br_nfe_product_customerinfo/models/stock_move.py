# Copyright 2026 KMEE (https://www.kmee.com.br)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class StockMove(models.Model):
    _inherit = "stock.move"

    @api.onchange("product_id")
    def _onchange_partner_product(self):
        for move in self:
            move.update(
                move._get_partner_product_vals(
                    move.product_id, move.picking_id.partner_id or move.partner_id
                )
                or {"partner_product_code": False, "partner_product_name": False}
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                vals.get("product_id")
                and not vals.get("partner_product_code")
                and not vals.get("partner_product_name")
            ):
                picking = self.env["stock.picking"].browse(vals.get("picking_id"))
                partner = picking.partner_id or self.env["res.partner"].browse(
                    vals.get("partner_id")
                )
                product = self.env["product.product"].browse(vals["product_id"])
                vals.update(self._get_partner_product_vals(product, partner))
        return super().create(vals_list)
