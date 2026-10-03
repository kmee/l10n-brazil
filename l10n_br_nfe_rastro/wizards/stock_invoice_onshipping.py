# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class StockInvoiceOnshipping(models.TransientModel):
    _inherit = "stock.invoice.onshipping"

    def _action_generate_invoices(self):
        invoices = super()._action_generate_invoices()
        invoices.invoice_line_ids._fill_nfe40_rastro()
        return invoices
