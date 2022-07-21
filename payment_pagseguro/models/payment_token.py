# Copyright 2020 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class PaymentTokenPagSeguro(models.Model):
    _inherit = "payment.token"

    pagseguro_card_holder_name = fields.Char(string="Pagseguro Card Holder")

    pagseguro_card_brand = fields.Char(string="Pagseguro Card Brand")

    pagseguro_card_token = fields.Char(string="Pagseguro Card Token")

    pagseguro_payment_method = fields.Char(string="Pagseguro Payment Method")

    pagseguro_installments = fields.Integer(string="Pagseguro Number of Installments")

    pagseguro_tx_id = fields.Char(string="Pagseguro PIX Transaction Id")
