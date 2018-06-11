# -*- coding: utf-8 -*-

from openerp import models, fields


class AccountJournal(models.Model):
    _inherit = 'account.journal'

    payment_mode = fields.Selection(
        (('card', 'Card'), ('check', 'Check')), 'Payment mode',
        help="Select the payment mode sent to the payment terminal")


class PosConfig(models.Model):
    _inherit = 'pos.config'

    iface_tef = fields.Boolean(
        'Payment Terminal',
        help="A payment terminal is available on the Proxy")
