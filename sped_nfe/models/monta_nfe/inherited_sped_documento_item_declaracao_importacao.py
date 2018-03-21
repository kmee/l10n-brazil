# -*- coding: utf-8 -*-
#
# Copyright 2016 Taŭga Tecnologia
#   Aristides Caldeira <aristides.caldeira@tauga.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from __future__ import division, print_function, unicode_literals

import logging
from odoo import api, models
from odoo.addons.l10n_br_base.constante_tributaria import (
    MODELO_FISCAL_NFCE,
    MODELO_FISCAL_NFE,
)

_logger = logging.getLogger(__name__)

try:
    from pybrasil.inscricao import limpa_formatacao
    from pybrasil.data import parse_datetime, UTC
    from pybrasil.valor.decimal import Decimal as D

except (ImportError, IOError) as err:
    _logger.debug(err)

from ..versao_nfe_padrao import ClasseDI, ClasseAdi


class SpedDocumentoItemDeclaracaoImportacao(models.Model):
    _inherit = 'sped.documento.item.declaracao.importacao'

    def monta_nfe(self):
        self.ensure_one()

        if self.documento_id.modelo != MODELO_FISCAL_NFE and \
                self.documento_id.modelo != MODELO_FISCAL_NFCE:
            return

        di = ClasseDI()

        di.nDI.valor = self.numero_documento
        di.dDI.valor = self.data_registro[:10]
        di.xLocDesemb.valor = self.local_desembaraco
        di.UFDesemb.valor = self.uf_desembaraco_id.uf
        di.dDesemb.valor = self.data_desembaraco[:10]
        di.tpViaTransp.valor = self.via_trans_internacional
        di.vAFRMM.valor = D(self.vr_afrmm)
        di.tpIntermedio.valor = self.forma_importacao

        if self.partner_id:
            di.CNPJ.valor = limpa_formatacao(self.partner_id.cnpj_cpf)
            di.UFTerceiro.valor = self.partner_id.estado
            di.cExportador.valor = \
                limpa_formatacao(self.partner_id.cnpj_cpf)

        #
        # Sempre existe pelo menos uma adição
        #
        adi = ClasseAdi()

        adi.nAdicao.valor = self.numero_adicao
        adi.nSeqAdic.valor = self.sequencial

        if self.partner_id:
            adi.cFabricante.valor = \
                limpa_formatacao(self.partner_id.cnpj_cpf)

        adi.vDescDI.valor = D(self.vr_desconto)
        adi.nDraw.valor = self.numero_drawback

        di.adi.append(adi)

        #
        # Agora, se houver mais
        #
        for adicao in self.adicao_ids:
            adi = ClasseAdi()

            adi.nAdicao.valor = adicao.numero_adicao
            adi.nSeqAdic.valor = adicao.sequencial

            if self.partner_id:
                adi.cFabricante.valor = \
                    limpa_formatacao(self.partner_id.cnpj_cpf)

            adi.vDescDI.valor = D(adicao.vr_desconto)
            adi.nDraw.valor = adicao.numero_drawback

            di.adi.append(adi)

        return di
