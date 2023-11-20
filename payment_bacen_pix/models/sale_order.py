#  Copyright 2023 KMEE
#  License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class SaleOrder(models.Model):
    _inherit = "sale.order"

    @api.multi
    def bacenpix_check_transaction(self):
        bacenpix_transactions = self.authorized_transaction_ids.filtered(
            lambda t: t.provider == "bacenpix" and t.state == 'authorized'
        )
        for transaction in bacenpix_transactions:
            transaction.action_bacenpix_check_transaction_status()

    def bacenpix_check_transactions(self):
        sale_orders = self.search([
            ("sistemica_state", "=", "awaiting_payment"),
            ("transaction_payment_method", "=", "PIX"),
        ])
        for sale in sale_orders:
            sale.bacenpix_check_transaction()
