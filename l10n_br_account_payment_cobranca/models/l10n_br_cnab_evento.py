# -*- coding: utf-8 -*-
# © 2012 KMEE INFORMATICA LTDA
#   @author  Luiz Felipe do Divino Costa <luiz.divino@kmee.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import logging
from odoo import models, fields
from .l10n_br_cnab import STATE

_logger = logging.getLogger(__name__)


class L10nBrCnabEvento(models.Model):
    _name = "l10n_br.cnab.evento"

    bank_payment_line_id = fields.Many2one(
        string="Bank Payment Line",
        comodel_name="bank.payment.line",
    )
    data_real_pagamento = fields.Date(
        string="Data do Crédito"
    )
    data_ocorrencia = fields.Date(
        string="Data da Ocorrência"
    )
    favorecido_conta_bancaria_id = fields.Many2one(
        string=u"Conta Bancária",
        comodel_name="res.partner.bank",
    )
    favorecido_id = fields.Many2one(
        string="Favorecido",
        comodel_name="res.partner"
    )
    identificacao_titulo_empresa = fields.Char(
        string="Identificação do Título da Empresa",
        required=False,
    )
    invoice_id = fields.Many2one(
        comodel_name='account.invoice',
        string='Fatura',
    )
    juros_mora_multa = fields.Float(
        string=u"Juros de Mora/Multa"
    )
    lote_id = fields.Many2one(
        string="Lote",
        comodel_name="l10n_br.cnab.lote",
        ondelete='cascade',
    )
    nosso_numero = fields.Char(
        string=u"Nosso Número"
    )
    ocorrencias = fields.Char(
        string=u"Ocorrências"
    )
    outros_creditos = fields.Float(
        string=u"Outros Créditos"
    )
    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Associado',
    )
    segmento = fields.Char(
        string="Segmento"
    )
    seu_numero = fields.Char(
        string=u"Seu Número"
    )
    state = fields.Selection(
        string="State",
        related="lote_id.state",
        selection=STATE,
        default="draft",
    )
    str_motiv_a = fields.Char(
        u'Motivo da ocorrência 01'
    )
    str_motiv_b = fields.Char(
        u'Motivo de ocorrência 02'
    )
    str_motiv_c = fields.Char(
        u'Motivo de ocorrência 03'
    )
    str_motiv_d = fields.Char(
        u'Motivo de ocorrência 04'
    )
    str_motiv_e = fields.Char(
        u'Motivo de ocorrência 05'
    )
    tipo_moeda = fields.Char(
        string=u"Tipo de Moeda"
    )
    tarifa_cobranca = fields.Float(
        string=u'Tarifa',
    )
    valor = fields.Float(
        string="Valor da Linha"
    )
    valor_abatimento = fields.Float(
        string="Valor do Abatimento",
        help="""Se o desconto ou abatimento é concedido na entrada do boleto 
        estes campos são retornados zerados(apesar de corretamente registrados 
        no Itaú). Se concedidos após a entrada, retornam com os valores
        do desconto ou abatimento.
        Na liquidação, desconto e abatimento retornam somados no campo 
        desconto; opcionalmente, mediante cadastro prévio em nosso sistema, 
        estes valores poderão retornar separados, conforme mostra o 
        indicador 36.4 do Item 5 - Condições Personalizadas."""
    )
    valor_desconto = fields.Float(
        string="Valor do Desconto",
        help="""Se o desconto ou abatimento é concedido na entrada do boleto 
        estes campos são retornados zerados(apesar de corretamente registrados 
        no Itaú). Se concedidos após a entrada, retornam com os valores
        do desconto ou abatimento.
        Na liquidação, desconto e abatimento retornam somados no campo 
        desconto; opcionalmente, mediante cadastro prévio em nosso sistema, 
        estes valores poderão retornar separados, conforme mostra o 
        indicador 36.4 do Item 5 - Condições Personalizadas."""
    )
    valor_iof = fields.Float(
        string="Valor do IOF"
    )
    valor_pagamento = fields.Float(
        string="Valor do Pagamento"
    )
