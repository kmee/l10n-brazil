# -*- coding: utf-8 -*-
# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from openerp import api, fields, models, _


class L10nBrAccountFiscalCategory(models.Model):

    _inherit = b'l10n_br_account.fiscal.category'

    financial_document_type_id = fields.Many2one(
        string='Tipo de documento',
        comodel_name='financial.document.type',
        ondelete='restrict',
    )
    financial_account_id = fields.Many2one(
        string='Conta financeira',
        comodel_name='financial.account',
        ondelete='restrict',
        domain=[('type', '=', 'A')],
    )
