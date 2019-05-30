# -*- coding: utf-8 -*-
# © 2012 KMEE INFORMATICA LTDA
#   @author Fernando Marcato <fernando.marcato@kmee.com.br>
#   @author  Hendrix Costa <hendrix.costa@kmee.com.br>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from __future__ import division, print_function, unicode_literals

from odoo import api, models, fields

from ..febraban.cnab import Cnab
from ..constantes import TIPO_SERVICO, FORMA_LANCAMENTO, \
    INDICATIVO_FORMA_PAGAMENTO, TIPO_MOVIMENTO, CODIGO_INSTRUCAO_MOVIMENTO

import logging

_logger = logging.getLogger(__name__)
try:
    from cnab240.errors import (Cnab240Error)
except ImportError as err:
    _logger.debug = err


class PaymentOrder(models.Model):
    _inherit = b'account.payment.order'

    file_number = fields.Integer(
        string=u'Número sequencial do arquivo',
    )

    cnab_file = fields.Binary(
        string='CNAB File',
        readonly=True,
    )

    cnab_filename = fields.Char("CNAB Filename")

    tipo_servico = fields.Selection(
        selection=TIPO_SERVICO,
        string=u'Tipo de Serviço',
        help=u'Campo G025 do CNAB',
        default='30',
    )
    forma_lancamento = fields.Selection(
        selection=FORMA_LANCAMENTO,
        string=u'Forma Lançamento',
        help=u'Campo G029 do CNAB'
    )
    codigo_convenio = fields.Char(
        size=20,
        string=u'Código do Convênio no Banco',
        help=u'Campo G007 do CNAB',
        default=u'0001222130126',
    )
    indicativo_forma_pagamento = fields.Selection(
        selection=INDICATIVO_FORMA_PAGAMENTO,
        string=u'Indicativo de Forma de Pagamento',
        help='Campo P014 do CNAB',
        default='01'
    )
    tipo_movimento = fields.Selection(
        selection=TIPO_MOVIMENTO,
        string='Tipo de Movimento',
        help='Campo G060 do CNAB',
        default='0',
    )
    codigo_instrucao_movimento = fields.Selection(
        selection=CODIGO_INSTRUCAO_MOVIMENTO,
        string='Código da Instrução para Movimento',
        help='Campo G061 do CNAB',
        default='0',
    )

    @api.model
    def _prepare_bank_payment_line(self, paylines):
        result = super(PaymentOrder, self)._prepare_bank_payment_line(paylines)
        result['nosso_numero'] = paylines.nosso_numero
        result['numero_documento'] = paylines.numero_documento
        result['communication'] = paylines.move_line_id.id
        return result

    @api.multi
    def open2generated(self):
        action = super(PaymentOrder, self).open2generated()
        if self.state == 'generated':
            for payment_line in self.payment_line_ids:
                payment_line.move_line_id.state_cnab = 'exported'
        return action

    @api.multi
    def generate_payment_file(self):
        """Returns (payment file as string, filename)"""
        self.ensure_one()
        if self.payment_method_id.code in ('240', '400', '500'):
            try:
                cnab = Cnab.get_cnab(
                    self.company_partner_bank_id.bank_id.code_bc,
                    self.payment_mode_id.payment_method_id.code
                )()
                return (cnab.remessa(self), self.name + '.REM')
            except Cnab240Error as e:
                from odoo import exceptions
                raise exceptions.ValidationError(
                    "Campo preenchido incorretamente \n\n{0}".format(e))
        return super(PaymentOrder, self).generate_payment_file()
