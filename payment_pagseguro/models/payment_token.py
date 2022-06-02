# Copyright 2020 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class PaymentTokenPagSeguro(models.Model):
    _inherit = "payment.token"

    card_holder = fields.Char(
        string="Holder",
        required=False,
    )

    pagseguro_card_token = fields.Char(
        string="Pagseguro card Token",
        required=False,
    )

    pagseguro_payment_method = fields.Char(
        string="Pagseguro payment method",
        required=False,
    )

    pagseguro_installments = fields.Integer(
        string="Pagseguro number of installments",
        required=False,
    )

    pagseguro_tx_id = fields.Char(string="Pagseguro transaction id", required=False)
