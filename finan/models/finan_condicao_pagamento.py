# -*- coding: utf-8 -*-
#
# Copyright 2017 Taŭga Tecnologia
#   Aristides Caldeira <aristides.caldeira@tauga.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

import logging

from dateutil.relativedelta import relativedelta
from odoo import api, fields, models
from ..constante_tributaria import (
    FORMA_PAGAMENTO,
    BANDEIRA_CARTAO,
    INTEGRACAO_CARTAO,
    INTEGRACAO_CARTAO_NAO_INTEGRADO,
    FORMA_PAGAMENTO_CARTOES,
    FORMA_PAGAMENTO_CARTAO_CREDITO,
    FORMA_PAGAMENTO_CARTAO_DEBITO,
    FORMA_PAGAMENTO_OUTROS,
    FORMA_PAGAMENTO_DICT,
    BANDEIRA_CARTAO_DICT,
)

_logger = logging.getLogger(__name__)

try:
    from pybrasil.valor.decimal import Decimal as D
    from pybrasil.valor import formata_valor
    from pybrasil.data import (
        dia_util_pagamento, hoje,
        DIA_SEGUNDA, DIA_TERCA, DIA_QUARTA, DIA_QUINTA, DIA_SEXTA,
        primeiro_dia_mes, ultimo_dia_mes, dias_uteis, meses
    )

except (ImportError, IOError) as err:
    _logger.debug(err)


class FinanCondicaoPagamento(models.Model):
    _name = 'finan.condicao.pagamento'
    _description = 'Condição de Pagamemento'
    _rec_name = 'nome_comercial'
    _order = 'sequence, nome'

    DIAS_UTEIS = (
        (str(DIA_SEGUNDA), 'Segundas-feiras'),
        (str(DIA_TERCA), 'Terças-feiras'),
        (str(DIA_QUARTA), 'Quartas-feiras'),
        (str(DIA_QUINTA), 'Quintas-feiras'),
        (str(DIA_SEXTA), 'Sextas-feiras'),
    )

    ADIA_ANTECIPA_DIA_UTIL = (
        ('P', 'Adia'),
        ('A', 'Antecipa'),
    )
    ADIA_DIA_UTIL = 'P'
    ANTECIPA_DIA_UTIL = 'A'

    DIAS_MES = (
        ('1', '1º'),
        # ('2', '2'),
        # ('3', '3'),
        # ('4', '4'),
        ('5', '5'),
        # ('6', '6'),
        # ('7', '7'),
        # ('8', '8'),
        # ('9', '9'),
        ('10', '10'),
        # ('11', '11'),
        # ('12', '12'),
        # ('13', '13'),
        # ('14', '14'),
        ('15', '15'),
        # ('16', '16'),
        # ('17', '17'),
        # ('18', '18'),
        # ('19', '19'),
        ('20', '20'),
        # ('21', '21'),
        # ('22', '22'),
        # ('23', '23'),
        # ('24', '24'),
        ('25', '25'),
        # ('26', '26'),
        # ('27', '27'),
        # ('28', '28'),
        # ('29', '29'),
        ('30', '30'),
        # ('31', '31'),
    )
    DIAS_MES_UTIL = (
        ('1', '1º'),
        # ('2', '2º'),
        # ('3', '3º'),
        # ('4', '4º'),
        ('5', '5º'),
        # ('6', '6º'),
        # ('7', '7º'),
        # ('8', '8º'),
        # ('9', '9º'),
        ('10', '10º'),
        # ('11', '11º'),
        # ('12', '12º'),
        # ('13', '13º'),
        # ('14', '14º'),
        ('15', '15º'),
        # ('16', '16º'),
        # ('17', '17º'),
        # ('18', '18º'),
        # ('19', '19º'),
        ('20', '20º'),
    )

    sequence = fields.Integer(
        default=10,
    )
    nome = fields.Char(
        string='Condição de pagamento',
        size=60,
        required=True,
        index=True
    )
    nome_comercial = fields.Char(
        string='Condição da pagamento',
        calcular_parcelas='_calcular_parcelas_nome_comercial',
    )
    em_parcelas_mensais = fields.Boolean(
        string='Em parcelas mensais?',
        default=True,
    )
    #
    # Configuração das datas de vencimento
    #
    meses = fields.Integer(
        string='Meses',
    )
    evitar_dia_semana = fields.Selection(
        selection=DIAS_UTEIS,
        string='Evitar vencimento às',
    )
    somente_dias_uteis = fields.Boolean(
        string='Somente dias úteis?',
    )
    antecipa_dia_util = fields.Selection(
        selection=ADIA_ANTECIPA_DIA_UTIL,
        string='Adia ou antecipa dia útil?',
        default=ADIA_DIA_UTIL,
    )
    todo_dia_mes = fields.Selection(
        selection=DIAS_MES,
        string='Vencimento todo dia',
    )
    todo_dia_mes_util = fields.Selection(
        selection=DIAS_MES_UTIL,
        string='Vencimento todo dia útil',
    )
    #
    # Configuração do valor das parcelas
    #
    com_entrada = fields.Boolean(
        string='Com entrada?',
    )
    al_entrada = fields.Float(
        string='Percentual de entrada',
        currency_field='currency_aliquota_id',
    )
    com_juros = fields.Boolean(
        string='Com juros?',
    )
    al_juros = fields.Float(
        string='Percentual de juros',
        currency_field='currency_aliquota_id',
    )
    forma_pagamento_id = fields.Many2one(
        comodel_name='finan.forma.pagamento',
        string='Forma de pagamento',
        required=True,
        index=True,
    )
    #
    # Campos para NF-e e SPED
    #
    forma_pagamento = fields.Selection(
        selection=FORMA_PAGAMENTO,
        string='Forma de pagamento',
        default=FORMA_PAGAMENTO_OUTROS,
    )
    bandeira_cartao = fields.Selection(
        selection=BANDEIRA_CARTAO,
        string='Bandeira do cartão',
    )
    integracao_cartao = fields.Selection(
        selection=INTEGRACAO_CARTAO,
        string='Integração do cartão',
        default=INTEGRACAO_CARTAO_NAO_INTEGRADO,
    )
    participante_id = fields.Many2one(
        string='Operadora do cartão',
        ondelete='restrict',
    )

    @api.multi
    def _calcular_parcelas_nome_comercial(self):
        valor = D(self.env.context.get('valor') or 0)

        for condicao in self:
            nome_comercial = ''
            if condicao.forma_pagamento in FORMA_PAGAMENTO_CARTOES:
                if condicao.forma_pagamento == \
                        FORMA_PAGAMENTO_CARTAO_CREDITO:
                    nome_comercial += '[Crédito '
                elif condicao.forma_pagamento == \
                        FORMA_PAGAMENTO_CARTAO_DEBITO:
                    nome_comercial += '[Débito '

                nome_comercial += \
                    BANDEIRA_CARTAO_DICT[condicao.bandeira_cartao]
                nome_comercial += '] '

            elif condicao.forma_pagamento:
                nome_comercial += '['
                nome_comercial += \
                    FORMA_PAGAMENTO_DICT[condicao.forma_pagamento]
                nome_comercial += '] '

            nome_comercial += condicao.nome

            if valor <= 0 or not condicao.em_parcelas_mensais:
                if condicao.com_entrada:
                    nome_comercial += ' com entrada '

                if condicao.com_juros and condicao.al_juros:
                    nome_comercial += ', com juros de '
                    nome_comercial += formata_valor(condicao.al_juros)
                    nome_comercial += '%'

                condicao.nome_comercial = nome_comercial
                continue

            meses = D(condicao.meses or 1)

            valor_entrada = D(0)
            if condicao.com_entrada:
                if self.env.context.get('valor_entrada'):
                    valor_entrada = D(self.env.context['valor_entrada'] or 0)
                elif condicao.al_entrada:
                    valor_entrada = \
                        valor * D(condicao.al_entrada) / 100

                valor_entrada = valor_entrada.quantize(D('0.01'))

                if valor_entrada > 0:
                    nome_comercial += ' com entrada de R$ '
                    nome_comercial += formata_valor(valor_entrada)

            valor_parcela, diferenca = condicao._calcula_valor_parcela(
                valor, meses, valor_entrada)

            if valor_parcela > 0:
                nome_comercial += ' de R$ '
                nome_comercial += formata_valor(valor_parcela)

            if condicao.com_juros and condicao.al_juros:
                nome_comercial += ', com juros de '
                nome_comercial += formata_valor(condicao.al_juros)
                nome_comercial += '%'

            condicao.nome_comercial = nome_comercial

    @api.depends('meses', 'com_entrada')
    def _onchange_meses(self):
        res = {}
        valores = {}
        res['value'] = valores

        #
        # Não pode ter entrada sendo somente 1 parcela
        #
        if meses <= 1:
            valores['com_entrada'] = False

        return res

    @api.onchange('forma_pagamento_id')
    def _onchange_forma_pagamento_id(self):
        for condicao in self:
            if not condicao.forma_pagamento_id:
                continue

            forma_pagamento = condicao.forma_pagamento_id
            condicao.forma_pagamento = forma_pagamento.forma_pagamento
            condicao.bandeira_cartao = forma_pagamento.bandeira_cartao
            condicao.integracao_cartao = forma_pagamento.integracao_cartao

            if forma_pagamento.participante_id:
                condicao.participante_id = \
                    forma_pagamento.participante_id
            else:
                condicao.participante_id = False

    def _verifica_dia_util(self, data):
        self.ensure_one()

        if self.somente_dias_uteis:
            if self.env.user.company_id.sped_empresa_id:
                empresa = self.env.user.company_id.sped_empresa_id
                if self.antecipa_dia_util == self.ANTECIPA_DIA_UTIL:
                    data = dia_util_pagamento(data, empresa.estado,
                                              empresa.cidade, antecipa=True)
                else:
                    data = dia_util_pagamento(data, empresa.estado,
                                              empresa.cidade)
            else:
                if self.antecipa_dia_util == self.ANTECIPA_DIA_UTIL:
                    data = dia_util_pagamento(data, antecipa=True)
                else:
                    data = dia_util_pagamento(data)

        if self.evitar_dia_semana and data.weekday() == \
                int(self.evitar_dia_semana):
            data += relativedelta(days=1)
            data = self._verifica_dia_util(data)

        return data

    def _verifica_dia_mes(self, data):
        self.ensure_one()

        if self.todo_dia_mes:
            data += relativedelta(day=int(self.todo_dia_mes))

        elif self.todo_dia_mes_util:
            if self.env.user.company_id.sped_empresa_id:
                empresa = self.env.user.company_id.sped_empresa_id
                dias = dias_uteis(primeiro_dia_mes(data), ultimo_dia_mes(data),
                                  empresa.estado, empresa.cidade)
            else:
                dias = dias_uteis(primeiro_dia_mes(data), ultimo_dia_mes(data))

            if int(self.todo_dia_mes_util) <= len(dias):
                data = dias[int(self.todo_dia_mes_util) - 1]

        return data

    def _calcula_valor_parcela(self, valor, meses, valor_entrada=0):
        self.ensure_one()

        #
        # Tratamento dos juros
        #
        if self.em_parcelas_mensais and self.com_juros and self.al_juros:
            al_juros = D(self.al_juros) / 100
            valor_parcela = D(0)

            if valor_entrada > 0:
                if meses > 1:
                    fator_juros = 1 - ((1 + al_juros) ** ((meses - 1) * -1))
                    fator_juros /= al_juros
                    valor_parcela = (valor - valor_entrada) / fator_juros
            else:
                fator_juros = 1 - ((1 + al_juros) ** (meses * -1))
                fator_juros /= al_juros
                valor_parcela = valor / fator_juros

            valor_parcela = valor_parcela.quantize(D('0.01'))

            if valor_entrada > 0:
                valor = valor_entrada + (valor_parcela * (meses - 1))
            else:
                valor = valor_parcela * meses

        #
        # Aponta o valor da parcela e a diferença em centavos a ser ajustada
        #
        if valor_entrada > 0:
            if meses > 1:
                valor_parcela = (valor - valor_entrada) / (meses - 1)
                valor_parcela = valor_parcela.quantize(D('0.01'))
                diferenca = valor - valor_entrada - \
                    (valor_parcela * (meses - 1))
        else:
            valor_parcela = valor / meses
            valor_parcela = valor_parcela.quantize(D('0.01'))
            diferenca = valor - (valor_parcela * meses)

        return valor_parcela, diferenca

    def calcular_parcelas(self, valor, data_base=False, entrada=0):
        self.ensure_one()

#        if not self.em_parcelas_mensais:
#            return super(AccountPaymentTerm, self).
#                   calcular_parcelas(valor,
#                                     date_ref=data_base)

        data_referencia = data_base or hoje()
        valor = D(valor)
        meses = D(self.meses or 1)
        res = []

        #
        # Tratamento do valor de entrada
        #
        valor_entrada = D(0)
        if self.com_entrada:
            if entrada:
                valor_entrada = D(entrada or 0)
            elif self.env.context.get('valor_entrada'):
                valor_entrada = D(self.env.context['valor_entrada'] or 0)
            elif self.al_entrada:
                valor_entrada = valor * D(self.al_entrada) / 100

        valor_entrada = valor_entrada.quantize(D('0.01'))

        valor_parcela, diferenca = \
            self._calcula_valor_parcela(valor, meses, valor_entrada)

        #
        # Gera as datas e valores de cada parcela
        #
        for i in range(meses):
            proxima_data = fields.Date.from_string(data_referencia)
            proxima_data += relativedelta(months=i + 1)
            proxima_data = self._verifica_dia_mes(proxima_data)
            proxima_data = self._verifica_dia_util(proxima_data)

            if valor_entrada > 0 and i == 0:
                parcela = [
                    fields.Date.to_string(proxima_data),
                    valor_entrada,
                ]
            else:
                parcela = [
                    fields.Date.to_string(proxima_data),
                    valor_parcela,
                ]

            if i == 0 and diferenca > 0:
                parcela[1] += diferenca
                diferenca = 0

            elif i + 1 == meses and diferenca != 0:
                parcela[1] += diferenca

            res.append(parcela)

        return res

    def gera_parcela_ids(self, valor, data_base):
        self.ensure_one()

        parcela_ids = [
            [5, False, {}],
        ]

        if not data_base:
            return parcela_ids

        valor = D(valor or 0)

        lista_vencimentos = self.calcular_parcelas(valor, data_base)

        parcela = 1
        for data_vencimento, valor in lista_vencimentos:
            duplicata = {
                'numero': str(parcela),
                'data_vencimento': data_vencimento,
                'valor': valor,
            }
            parcela_ids.append([0, False, duplicata])
            parcela += 1

        return parcela_ids
