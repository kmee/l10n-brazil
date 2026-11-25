# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models

# Fiscal values of the order line that do not depend on the partner.
KEEP_FISCAL_FIELDS = {
    "product_id",
    "uom_id",
    "uot_id",
    "quantity",
    "fiscal_quantity",
    "price_unit",
    "fiscal_price",
    "fiscal_operation_id",
    "ncm_id",
    "nbs_id",
    "nbm_id",
    "cest_id",
    "service_type_id",
    "city_taxation_code_id",
    "national_taxation_code_id",
    "discount_value",
    "freight_value",
    "insurance_value",
    "other_value",
    "name",
    "company_id",
    "currency_id",
    "icms_origin",
    "fiscal_genre_id",
    "fiscal_type",
    "operation_indicator_id",
}


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _prepare_invoice_line(self, **optional_values):
        vals = super()._prepare_invoice_line(**optional_values)
        order = self.order_id
        if self.display_type or not order._invoice_plan_payer_recompute_fiscal():
            return vals
        # Leave out what was computed for the customer of the order (operation
        # line, CFOP, taxes, final consumer) so that the invoice line
        # computes it for the payer.
        mixin_fields = self.env["l10n_br_fiscal.document.line.mixin"]._fields
        for fname in list(vals):
            if fname in mixin_fields and fname not in KEEP_FISCAL_FIELDS:
                del vals[fname]
        vals.pop("tax_ids", None)
        vals["partner_id"] = order._get_invoice_plan_payer().id
        return vals
