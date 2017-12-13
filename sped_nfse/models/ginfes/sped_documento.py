# -*- coding: utf-8 -*-
# Copyright 2017 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _
from odoo import exceptions
import re
import datetime
from decimal import Decimal
import os

from odoo.addons.l10n_br_base.constante_tributaria import (
    TIPO_EMISSAO_NFE_NORMAL,
    AMBIENTE_NFE_PRODUCAO,
    SITUACAO_NFE_ENVIADA,
    SITUACAO_NFE_REJEITADA,
    SITUACAO_NFE_CANCELADA,
)

from pytrustnfe.nfse.ginfes import xml_recepcionar_lote_rps
from pytrustnfe.nfse.ginfes import recepcionar_lote_rps
from pytrustnfe.nfse.ginfes import consultar_situacao_lote
from pytrustnfe.nfse.ginfes import consultar_lote_rps
from pytrustnfe.nfse.ginfes import cancelar_nfse
from pytrustnfe.nfse.ginfes import xml_cancelar_nfse

from lxml import etree
from odoo.addons.l10n_br_base.constante_tributaria import (
    MODELO_FISCAL_NFSE,
)

DIRNAME = os.path.dirname(__file__)


class SpedDocumento(models.Model):

    _inherit = 'sped.documento'

    numero_rps = fields.Char(
        string='Número da RPS'
    )

    @api.onchange('empresa_id', 'modelo', 'emissao')
    def _onchange_empresa_id(self):
        res = super(SpedDocumento, self)._onchange_empresa_id()
        if not res:
            res = {'value': {}}
        if self.modelo == MODELO_FISCAL_NFSE:
            res['value']['ambiente_nfe'] = self.empresa_id.ambiente_nfse
            res['value']['tipo_emissao_nfe'] = TIPO_EMISSAO_NFE_NORMAL

            if self.empresa_id.ambiente_nfse == AMBIENTE_NFE_PRODUCAO:
                res['value']['serie'] = self.empresa_id.serie_rps_producao
            else:
                res['value']['serie'] = self.empresa_id.serie_rps_homologacao


            return res

    @api.onchange('empresa_id', 'modelo', 'emissao', 'serie', 'ambiente_nfe')
    def _onchange_serie(self):
        res = super(SpedDocumento, self)._onchange_serie()

        if self.modelo == MODELO_FISCAL_NFSE and not self.numero_rps:
            rps = self.empresa_id.ultimo_rps._next()
            res['value']['numero_rps'] = rps

        return res

    def envia_nfe(self):
        self.ensure_one()
        result = super(SpedDocumento, self).envia_nfe()
        if self.modelo not in (MODELO_FISCAL_NFSE) or\
                self.empresa_id.provedor_nfse != 'ginfes':
            return result

        self.envia_rps()

    def envia_rps(self):
        pfx = self.empresa_id.certificado_id.certificado_nfse()

        dados_nfse = self.monta_lote_rps()

        lote_rps = xml_recepcionar_lote_rps(
            certificado=pfx, nfse=dados_nfse,
            ambiente=self.empresa_id.ambiente_nfse)

        erros = self.validar_schema(
            lote_rps, 'servico_enviar_lote_rps_envio_v03.xsd')

        if not erros:
            retorno = recepcionar_lote_rps(certificado=pfx, xml=lote_rps,
                                       ambiente=self.empresa_id.ambiente_nfse)
        else:
            raise exceptions.UserError('Erro de validação do xml: \n' + erros)

        obj_retorno = retorno['object']

        if hasattr(obj_retorno, 'Protocolo'):
            self.situacao_nfe = SITUACAO_NFE_ENVIADA
            self.protocolo_autorizacao = obj_retorno.Protocolo
            self.data_hora_autorizacao = datetime.datetime.strptime(
                obj_retorno.DataRecebimento.text, '%Y-%m-%dT%H:%M:%S')

        elif hasattr(obj_retorno, 'ListaMensagemRetorno'):
            obj_retorno = obj_retorno.ListaMensagemRetorno.MensagemRetorno
            msg = obj_retorno.Codigo + ' - '
            msg += obj_retorno.Mensagem + ' - '
            msg += obj_retorno.Correcao
            self.mensagem_nfe = msg
            self.situacao_nfe = SITUACAO_NFE_REJEITADA

    def consulta_nfse(self):
        pfx = self.empresa_id.certificado_id.certificado_nfse()
        consulta = self._monta_consulta()

        consulta_situacao = consultar_situacao_lote(
            pfx, consulta=consulta, ambiente=self.empresa_id.ambiente_nfse)

        ret_sit = consulta_situacao['object']

        if hasattr(ret_sit, 'Situacao'):
            if ret_sit.Situacao in [3, 4]:
                consulta_lote = consultar_lote_rps(
                    pfx, consulta=consulta,
                    ambiente=self.empresa_id.ambiente_nfse)

                ret_lote = consulta_lote['object']

                if hasattr(ret_lote,'ListaNfse'):
                    self.situacao_nfe = 'autorizada'
                    self.numero = ret_lote.ListaNfse.CompNfse.\
                        Nfse.InfNfse.CodigoVerificacao

                elif hasattr(ret_lote, 'ListaMensagemRetorno'):
                    obj_retorno = ret_lote.ListaMensagemRetorno.MensagemRetorno
                    msg = obj_retorno.Codigo + ' - '
                    msg += obj_retorno.Mensagem + ' - '
                    msg += obj_retorno.Correcao
                    self.mensagem_nfe = msg
                    self.situacao_nfe = 'rejeitada'

        elif hasattr(ret_sit, 'ListaMensagemRetorno'):
            obj_retorno = ret_sit.ListaMensagemRetorno.MensagemRetorno
            msg = obj_retorno.Codigo + ' - '
            msg += obj_retorno.Mensagem + ' - '
            msg += obj_retorno.Correcao
            self.mensagem_nfe = msg
            self.situacao_nfe = 'rejeitada'

    def cancela_nfse(self):
        #
        # Parece que a Ginfes desabilitou o serviço de cancelamento
        #
        #
        raise exceptions.Warning('Serviço não disponível pelo '
                                 'provedor, utilize o site para '
                                 'realizar o cancelamento')

        pfx = self.empresa_id.certificado_id.certificado_nfse()

        empresa = self.empresa_id

        dados_canc = {
            'cnpj_prestador': re.sub('[^0-9]', '', empresa.cnpj_cpf),
            'inscricao_municipal': re.sub('[^0-9]', '', empresa.im),
            'cidade': empresa.municipio_id.codigo_ibge.rstrip('0'),
            'numero_nfse': str(int(self.numero)),
            'codigo_cancelamento': '2',
        }

        xml_canc = str(xml_cancelar_nfse(
            certificado=pfx, cancelamento=dados_canc,
            ambiente=self.empresa_id.ambiente_nfse))

        erros = self.validar_schema(
            xml_canc, 'servico_cancelar_nfse_envio_v03.xsd')

        if not erros:
            retorno = cancelar_nfse(
                certificado=pfx, xml=xml_canc,
                ambiente=self.empresa_id.ambiente_nfse)
        else:
            raise exceptions.UserError('Erro de validação do xml: \n' + erros)

        obj_retorno = retorno['object']

        if hasattr(obj_retorno, 'Cancelamento'):
            self.situacao_nfe = SITUACAO_NFE_CANCELADA
            self.mensagem_nfe = u'Nota Fiscal de Serviço Cancelada'

        else:
            # E79 - Nota já está cancelada
            if obj_retorno.ListaMensagemRetorno.MensagemRetorno.Codigo == 'E79':
                self.situacao_nfe = SITUACAO_NFE_CANCELADA
                self.mensagem_nfe = u'Nota Fiscal de Serviço Cancelada'

            else:
                erro_retorno = obj_retorno.ListaMensagemRetorno.MensagemRetorno
                msg = 'Erro no cancelamento - '
                msg += erro_retorno.Codigo + ' - '
                msg += erro_retorno.Mensagem + ' - '
                msg += erro_retorno.Correcao
                self.mensagem_nfe = msg

    def _monta_rps_tomador(self):
        participante = self.participante_id

        return {
            'tipo_cpfcnpj': 1 if participante.tipo_pessoa == 'F' else 2,
            'cnpj_cpf': re.sub('[^0-9]', '', participante.cnpj_cpf or ''),
            'razao_social': participante.razao_social or '',
            'logradouro': participante.endereco or '',
            'numero': participante.numero or '',
            'complemento': participante.complemento or '',
            'bairro': participante.bairro or 'Sem Bairro',
            'cidade': int(participante.municipio_id.codigo_ibge[:7]),
            'cidade_descricao': participante.municipio_id.nome or '',
            'uf': participante.estado or '',
            'cep': re.sub('[^0-9]', '', participante.cep),
            'inscricao_municipal': re.sub('[^0-9]', '', participante.im or ''),
            'email': participante.email or '',
        }

    def _monta_rps_prestador(self):
        participante = self.empresa_id

        return {
            'cnpj': re.sub('[^0-9]', '', participante.cnpj_cpf or ''),
            'inscricao_municipal': re.sub('[^0-9]', '', participante.im or ''),
        }

    @staticmethod
    def formata_campo_valor(valor):
        return str(Decimal(valor).quantize(Decimal('.01')))

    def _monta_rps_servico(self):
        itens = self.item_ids
        aliquota_iss_obj = self.env['sped.aliquota.iss']
        codigo_trib_municipio = aliquota_iss_obj.search([
                ('servico_id', '=', itens[0].produto_id.servico_id.id),
                ('municipio_id', '=', self.participante_id.municipio_id.id),]
        )
        codigo_servico = itens[0].produto_id.servico_id.codigo.lstrip('0')

        # Hardcoded
        valor_iss = codigo_trib_municipio.al_iss * self.vr_operacao

        servico = {
            # totais
            'valor_servico': self.formata_campo_valor(self.vr_operacao),
            'valor_deducao': self.formata_campo_valor(self.vr_desconto),
            # TODO: campos calculados para retenções
            # 'valor_pis': self.formata_campo_valor(self.vr_pis_retido),
            # 'valor_cofins': self.formata_campo_valor(self.vr_cofins_retido),
            # 'valor_inss': self.formata_campo_valor(self.vr_inss_retido),
            # 'valor_ir': self.formata_campo_valor(self.vr_irrf_retido),
            # 'valor_csll': self.formata_campo_valor(self.vr_csll_retido),
            'iss_retido': '1' if itens[0].cst_iss == 'R' else '2',
            'valor_iss': self.formata_campo_valor(valor_iss),
            # 'outras_retencoes': '', # TODO
            'base_calculo': self.formata_campo_valor(self.vr_operacao),
            'aliquota_issqn': codigo_trib_municipio.al_iss,
            # 'valor_liquido_nfse': self.formata_campo_valor(self.vr_nf),
            'valor_iss_retido': self.formata_campo_valor(valor_iss) if
            itens[0].cst_iss == 'R' else '',
            # 'desconto_incondicionado': '', # TODO
            # 'desconto_condicionado': '', # TODO
            'codigo_servico': codigo_servico,
            # 'cnae_servico': '', # TODO
            'codigo_tributacao_municipio': codigo_trib_municipio.codigo or
                                           codigo_servico,
            'descricao': ''.join(
                [(item.produto_descricao + '\n') for item in itens]),

        }
        return servico

    def monta_lote_rps(self):
        empresa = self.empresa_id
        tomador = self._monta_rps_tomador()
        prestador = self._monta_rps_prestador()
        servico = self._monta_rps_servico()
        data_emissao = fields.Datetime.context_timestamp(
            self, fields.Datetime.from_string(self.data_hora_emissao))

        rps = [
            {
                'natureza_operacao': int(self.natureza_tributacao_nfse) + 1,
                'optante_simples': '1' if self.empresa_id.regime_tributario in
                                          ('1', '2') else '2',
                'incentivador_cultural': '2', # TODO: automatizar seleção
                'numero': int(self.numero_rps),
                'serie': self.serie,
                'tipo_rps': '1', # TODO: opções para substituir nota
                'data_emissao': data_emissao.strftime('%Y-%m-%dT%H:%M:%S'),
                'status': '1', # TODO
                'codigo_municipio': tomador.get('cidade'),
                'tomador': tomador,
                'prestador': prestador,
            }
        ]
        rps[0].update(servico)

        lote_rps = {
            'numero_lote': self.empresa_id.ultimo_lote_rps._next(),
            'cnpj_prestador': re.sub('[^0-9]', '', empresa.cnpj_cpf or ''),
            'inscricao_municipal': re.sub('[^0-9]', '', empresa.im or ''),
            'lista_rps': rps,
        }

        return lote_rps

    def _monta_consulta(self):
        return {
            'cnpj_prestador': re.sub(
                '[^0-9]', '', self.empresa_id.cnpj_cpf or ''),
            'inscricao_municipal': re.sub(
                '[^0-9]', '', self.empresa_id.im or ''),
            'protocolo': self.protocolo_autorizacao,
        }

    def validar_schema(self, xml, arquivo_esquema):
        path_arquivo = DIRNAME + '/schemas_v301/' + arquivo_esquema

        esquema = etree.XMLSchema(etree.parse(path_arquivo))
        esquema.validate(etree.fromstring(xml))

        retorno = "\n".join(
            [x.message for x in esquema.error_log])
        return retorno
