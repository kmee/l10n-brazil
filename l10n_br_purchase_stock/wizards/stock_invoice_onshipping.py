# Copyright 2020 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class StockInvoiceOnshipping(models.TransientModel):

    _inherit = 'stock.invoice.onshipping'

    @api.multi
    def _get_invoice_line_values(self, moves, invoice_values, invoice):
        move = fields.first(moves)
        values = super()._get_invoice_line_values(
            moves, invoice_values, invoice
        )

        if move.purchase_line_id:
            values['purchase_line_id'] = move.purchase_line_id.id

            values['invoice_line_tax_ids'] = [
                (6, 0, self.env['l10n_br_fiscal.tax'].browse(
                    values['fiscal_tax_ids'][0][2]
                ).account_taxes(user_type='purchase').ids)
            ]
        return values
