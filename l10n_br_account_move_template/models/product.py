# -*- coding: utf-8 -*-
# Copyright (C) 2013  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from openerp import models, fields, api

from openerp.addons.l10n_br_account_product_service.models\
    .l10n_br_account_product_service import (
    PRODUCT_FISCAL_TYPE_DEFAULT,
    PRODUCT_ACCOUNT_TYPE)

class ProductTemplate(models.Model):
    """Inherit class to change default value of fiscal_type field"""
    _inherit = 'product.template'

    account_type = fields.Selection(PRODUCT_ACCOUNT_TYPE,
                                   u'Tipo Contábil',
                                   required=True,
                                   default=PRODUCT_FISCAL_TYPE_DEFAULT)

    @api.depends('account_type')
    def compute_fiscal_type(self):
        for record in self:
            if record.account_type == 'service':
                record.fiscal_type = 'service'
            else:
                record.fiscal_type = 'product'