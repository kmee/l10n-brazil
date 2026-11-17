# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def _invoice_plan_payer_recompute_fiscal(self):
        """The fiscal data of the order was computed for the invoice address;
        an invoice to another payer must compute its own."""
        self.ensure_one()
        payer = self._get_invoice_plan_payer()
        return (
            bool(payer)
            and payer.commercial_partner_id
            != self.partner_invoice_id.commercial_partner_id
        )

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self._invoice_plan_payer_recompute_fiscal():
            vals.pop("ind_final", None)
        return vals
