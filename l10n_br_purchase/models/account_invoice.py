# Copyright (C) 2020  Magno Costa - Akretion
# Copyright (C) 2020  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, models


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    def _prepare_invoice_line_from_po_line(self, line):
        values = line._prepare_br_fiscal_dict(default=False)
        values.update(super()._prepare_invoice_line_from_po_line(line))
        seller = line.product_id._select_seller(
            partner_id=line.partner_id,
            quantity=line.product_qty,
            date=line.order_id.date_order and line.order_id.date_order.date(),
            uom_id=line.product_uom
        )
        values['product_name'] = seller.product_name
        values['product_code'] = seller.product_code
        values['qty_received'] = line.product_qty \
            if line.product_id.purchase_method == 'purchase' \
            else line.qty_received
        values['entry_uom_id'] = line.product_uom
        values['entry_cfop_id'] = line.cfop_id
        return values

    @api.onchange('purchase_id')
    def purchase_order_change(self):
        if self.purchase_id:
            self.fiscal_operation_id = self.purchase_id.fiscal_operation_id
        return super().purchase_order_change()
