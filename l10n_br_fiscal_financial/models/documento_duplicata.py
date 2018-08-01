# -*- coding: utf-8 -*-
#
# Copyright 2016 Taŭga Tecnologia
#   Aristides Caldeira <aristides.caldeira@tauga.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from __future__ import division, print_function, unicode_literals

from openerp import api, fields, models
from openerp.addons.financial.constants import (
    FINANCIAL_DEBT_2PAY,
    FINANCIAL_DEBT_2RECEIVE
)


class SpedDocumentoDuplicata(models.Model):
    _name = b'sped.documento.duplicata'
    _description = 'Duplicatas do Documento Fiscal'
    _order = 'invoice_id, data_vencimento'
    # _rec_name = 'numero'

    invoice_id = fields.Many2one(
        string='Documento',
        comodel_name='account.invoice',
        ondelete='cascade',
    )
    payment_term_id = fields.Many2one(
        string='Pagamento',
        comodel_name='account.payment.term',
        ondelete='cascade',
    )
    numero = fields.Char(
        string='Número',
        size=60,
        required=True,
    )
    data_vencimento = fields.Date(
        string='Data de vencimento',
        required=True,
    )
    valor = fields.Float(
        string='Valor',
        digits=(18, 2),
        required=True,
    )

    @api.depends('payment_term_id', 'invoice_id')
    def _check_payment_term_id_invoice_id(self):
        for duplicata in self:
            if duplicata.payment_term_id:
                if not duplicata.invoice_id:
                    duplicata.invoice_id = \
                        duplicata.payment_term_id.invoice_id.id
                elif duplicata.invoice_id.id != \
                        duplicata.payment_term_id.invoice_id.id:
                    duplicata.invoice_id = \
                        duplicata.payment_term_id.invoice_id.id

    financial_move_ids = fields.One2many(
        comodel_name='financial.move',
        inverse_name='sped_documento_duplicata_id',
        string='Lançamentos Financeiros',
        copy=False
    )

    def prepara_financial_move(self):

        moeda_empresa_id = self.invoice_id.company_id.currency_id
        moeda_documento_id = self.invoice_id.currency_id

        moeda_sao_diferentes = moeda_documento_id != moeda_empresa_id
        if moeda_sao_diferentes:
            moeda_finaceiro_id = moeda_empresa_id
        else:
            moeda_finaceiro_id = moeda_documento_id

        valor_documento = self.valor

        dados = {
            'date_document': self.invoice_id.date_invoice,
            # 'participante_id': self.invoice_id.participante_id,
            'partner_id': self.invoice_id.partner_id.id,
            # 'empresa_id': self.invoice_id.empresa_id.id,
            'company_id': self.invoice_id.company_id.id,
            'doc_source_id': 'account.invoice,' + str(self.invoice_id.id),
            'sped_invoice_id': self.invoice_id.id,
            'sped_documento_duplicata_id': self.id,
            'document_type_id':
                self.invoice_id.fiscal_category_id.
                    financial_document_type_id.id,
            'account_id': self.invoice_id.fiscal_category_id.
                financial_account_id.id,
            'date_maturity': self.data_vencimento,
            'amount_document': valor_documento,
            'currency_id': moeda_finaceiro_id.id,
            'document_number':
                '{0.serie_nfe}-{0.number}-{1.numero}/{2}'.format(
                    self.invoice_id, self,
                    unicode(len(self.invoice_id.duplicata_ids))),
            'account_move_id': self.invoice_id.move_id.id,
            'journal_id': self.invoice_id.journal_id.id,
            'payment_term_id': self.invoice_id.payment_term.id,
            'sped_forma_pagamento_id':
                self.invoice_id.payment_term.sped_forma_pagamento_id.id,
        }

        if moeda_sao_diferentes:
            #
            # Converte o valor usando a cotação mais recente.
            #
            taxa_conversao = moeda_empresa_id._get_conversion_rate(self, moeda_documento_id)
            valor_estrangeiro = moeda_documento_id.compute(valor_documento, moeda_empresa_id)

            dados['original_currency_amount'] = valor_estrangeiro
            dados['currency_rate'] = taxa_conversao
            dados['original_currency_id'] = moeda_documento_id.id

        if self.invoice_id.type in ('out_invoice', 'out_refund'):
            dados['type'] = FINANCIAL_DEBT_2RECEIVE
        else:
            dados['type'] = FINANCIAL_DEBT_2PAY
        return dados
