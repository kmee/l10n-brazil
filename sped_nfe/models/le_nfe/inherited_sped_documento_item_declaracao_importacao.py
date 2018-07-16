# -*- coding: utf-8 -*-
#
# Copyright 2016 Taŭga Tecnologia
#   Aristides Caldeira <aristides.caldeira@tauga.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from __future__ import division, print_function, unicode_literals

import logging
from odoo import api, models, fields
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

        if self.item_id.documento_id.modelo != MODELO_FISCAL_NFE and \
                self.item_id.documento_id.modelo != MODELO_FISCAL_NFCE:
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

        if self.participante_id:
            di.CNPJ.valor = limpa_formatacao(self.participante_id.cnpj_cpf)
            if not 'EX' in self.participante_id.municipio_id.estado_id.uf:
                di.UFTerceiro.valor = \
                    self.participante_id.municio_id.estado_id.uf
            di.cExportador.valor = \
                limpa_formatacao(self.participante_id.cnpj_cpf)

        #
        # Sempre existe pelo menos uma adição
        #
        adi = ClasseAdi()

        adi.nAdicao.valor = self.numero_adicao
        adi.nSeqAdic.valor = self.sequencial

        if self.participante_id:
            adi.cFabricante.valor = \
                limpa_formatacao(self.participante_id.cnpj_cpf)

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

            if self.participante_id:
                adi.cFabricante.valor = \
                    limpa_formatacao(self.participante_id.cnpj_cpf)

            adi.vDescDI.valor = D(adicao.vr_desconto)
            adi.nDraw.valor = adicao.numero_drawback

            di.adi.append(adi)

        return di

    def le_nfe(self, di, participante=False):
        dados = {}
        dados['numero_documento'] = di.nDI.valor
        dados['data_registro'] = fields.Date.to_string(di.dDI.valor)
        dados['local_desembaraco'] = di.xLocDesemb.valor  # TODO: buscar local
        dados['uf_desembaraco_id']= self.env['sped.estado'].search([
            ('uf', '=', di.UFDesemb.valor)]).id
        dados['data_desembaraco'] = fields.Date.to_string(di.dDesemb.valor)
        dados['via_trans_internacional'] = di.tpViaTransp.valor
        dados['vr_afrmm'] = D(di.vAFRMM.valor)
        dados['forma_importacao'] = di.tpIntermedio.valor

        #busca participante
        dados['participante_id'] = self.env['sped.participante'].search(
            [
                ('cnpj_cpf', '=', di.CNPJ.valor),
            ]
        )
        if not dados['participante_id']:
            dados['participante_id'] = participante

        #
        # Sempre existe pelo menos uma adição
        #
        dados['numero_adicao'] = di.adi[0].nAdicao.valor
        dados['sequencial'] = di.adi[0].nSeqAdic.valor
        dados['vr_desconto'] = di.adi[0].vDescDI.valor
        dados['numero_drawback'] = di.adi[0].nDraw.valor

        #
        # Se houver mais
        #
        # if len(di.adi) > 1:
        #     dados['adicao_ids'] = self.le_nfe_di_adicao(di.adi.pop(di.adi[0]))

        return dados

    def le_nfe_di_adicao(self, adicao):
        adicoes = []
        particip = self.env['sped.participante'].search([
                ('cnpj_cpf', '=', adicao.cFabricante.valor)])
        dados_adi = {
            'numero_adicao': adicao.nAdicao.valor,
            'sequencial': adicao.nSeqAdic.valor,
            'participante_id': particip,
            'vr_desconto': adicao.vDescDI.valor,
            'numero_drawback': adicao.nDraw.valor,
        }
        adicoes.append((0,0, dados_adi))

        return adicoes
