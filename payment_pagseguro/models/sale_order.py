#  Copyright 2022 KMEE
#  License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.multi
    def pagseguro_check_transaction(self):
        pagseguro_transactions = self.authorized_transaction_ids.filtered(
            lambda t: t.provider == "pagseguro" and t.state == 'authorized'
        )
        for transaction in pagseguro_transactions:
            if transaction.pagseguro_s2s_check_link:
                transaction.pagseguro_check_transaction()

    def pagseguro_check_transactions(self):
        sale_orders = self.search([
            ("sistemica_state", "=", "awaiting_payment"),
            ("transaction_payment_method", "in", ("BOLETO", "CREDIT_CARD")),
        ])
        for sale in sale_orders:
            sale.pagseguro_check_transaction()
