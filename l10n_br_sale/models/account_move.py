# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def default_get(self, fields_list):
        """A customer invoice opened by hand suggests the sale fiscal operation of
        the company, as the sale order does; the user can still change it while
        the invoice is a draft."""
        res = super().default_get(fields_list)
        if "fiscal_operation_id" in fields_list and not res.get("fiscal_operation_id"):
            move_type = res.get("move_type") or self.env.context.get(
                "default_move_type"
            )
            operation = self.env.company.sale_fiscal_operation_id
            if move_type == "out_invoice" and operation:
                res["fiscal_operation_id"] = operation.id
        return res
