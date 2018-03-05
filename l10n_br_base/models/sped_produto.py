# -*- coding: utf-8 -*-
#
# Copyright 2016 Taŭga Tecnologia -
#   Aristides Caldeira <aristides.caldeira@tauga.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from __future__ import division, print_function, unicode_literals

import logging

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import odoo.addons.decimal_precision as dp
from .sped_base import SpedBase
from ..constante_tributaria import (
    ORIGEM_MERCADORIA,
    TIPO_PRODUTO_SERVICO,
    TIPO_PRODUTO_SERVICO_MATERIAL_USO_CONSUMO,
    TIPO_PRODUTO_SERVICO_SERVICOS,
)

_logger = logging.getLogger(__name__)

try:
    from pybrasil.produto import valida_ean
    from pybrasil.base import tira_acentos

except (ImportError, IOError) as err:
    _logger.debug(err)


class SpedProduto(SpedBase, models.Model):
    _name = b'sped.produto'
    _description = 'Produtos e serviços'
    _inherits = {'product.product': 'product_id'}
    _inherit = ['mail.thread']
    _order = 'nome, codigo'
    _rec_name = 'nome'

    product_id = fields.Many2one(
        comodel_name='product.product',
        string='Product original',
        ondelete='restrict',
        required=True,
    )
    # company_id = fields.Many2one(
    # 'res.company', string='Empresa', ondelete='restrict')

    @api.model
    def create(self, vals):
        produto = super(SpedProduto, self.with_context(
            create_sped=True)).create(vals)
        return produto