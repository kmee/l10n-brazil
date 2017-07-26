# -*- coding: utf-8 -*-
# Copyright (C) 2013  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from openerp import models, fields

PRODUCT_FISCAL_TYPE = [
    ('service', u'Serviço'),
    ('product', 'Produto'),
]
PRODUCT_ACCOUNT_TYPE = [
    ('revenda', u'Mercadoria para Revenda'),
    ('prima', u'Matéria - Prima'),
    ('processo', u'Produto em Processo'),
    ('embalagem', u'Embalagem'),
    ('acabado', u'Produto Acabado'),
    ('subproduto', u'Subproduto'),
    ('intermediario', u'Produto Intermediário'),
    ('consumo', u'Material de Uso e Consumo'),
    ('ativo', u'Ativo Imobilizado'),
    ('insumos', u'Outros Insumos'),
    ('outro', u'Outras'),
    ('service', u'Serviço'),
]

PRODUCT_FISCAL_TYPE_DEFAULT = PRODUCT_FISCAL_TYPE[0][0]


class L10n_brAccountFiscalCategory(models.Model):
    """Inherit class to change default value of fiscal_type field"""
    _inherit = 'l10n_br_account.fiscal.category'

    fiscal_type = fields.Selection(PRODUCT_FISCAL_TYPE,
                                   u'Tipo Fiscal',
                                   required=True,
                                   default=PRODUCT_FISCAL_TYPE_DEFAULT)


class L10n_brAccountDocumentSerie(models.Model):
    """Inherit class to change default value of fiscal_type field"""
    _inherit = 'l10n_br_account.document.serie'

    fiscal_type = fields.Selection(PRODUCT_FISCAL_TYPE,
                                   u'Tipo Fiscal',
                                   required=True,
                                   default=PRODUCT_FISCAL_TYPE_DEFAULT)
