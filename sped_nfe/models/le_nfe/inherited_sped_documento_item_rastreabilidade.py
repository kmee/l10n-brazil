# -*- coding: utf-8 -*-
#
# Copyright 2016 Taŭga Tecnologia
#   Aristides Caldeira <aristides.caldeira@tauga.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

# from .versao_nfe_padrao import ClasseRastro

from __future__ import division, print_function, unicode_literals

import logging
from odoo import models
from odoo.addons.l10n_br_base.constante_tributaria import (
    MODELO_FISCAL_NFE,
)

_logger = logging.getLogger(__name__)


class SpedDocumentoItemRastreabilidade(models.Model):
    _inherit = 'sped.documento.item.rastreabilidade'

    def monta_nfe(self):
        self.ensure_one()

        if self.documento_id.modelo != MODELO_FISCAL_NFE:
            return

        rastro = 0

        # rastro = Rastro_400()
        #
        # rastro.nLote.valor = self.numero
        # rastro.qLote.valor = D(self.quantidade)
        # rastro.xLocDesemb.valor = self.local_desembaraco
        # rastro.dFab.valor = self.data_fabricacao[:10]
        # rastro.dVal.valor = self.data_validade[:10]
        # rastro.cAgreg.valor = self.codigo_agregacao or ''
        #
        return rastro
