# -*- coding: utf-8 -*-
# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from openerp import api, fields, models, _


class AccountInvoice(models.Model):
    _inherit = b'account.invoice'

    @api.multi
    def _compute_financial_ids(self):
        for record in self:
            document_id = record._name + ',' + str(record.id)
            record.financial_ids = record.env['financial.move'].search(
                [['doc_source_id', '=', document_id]]
            )

    financial_ids = fields.One2many(
        string='Financial Items',
        comodel_name='financial.move',
        compute='_compute_financial_ids',
        readonly=True,
        copy=False
    )
    duplicata_ids = fields.One2many(
        string='Duplicatas',
        comodel_name='sped.documento.duplicata',
        inverse_name='invoice_id',
    )

    @api.onchange('payment_term', 'date_invoice', 'amount_net',
                  'amount_total', 'duplicata_ids')
    def onchange_duplicatas(self):
        res = {}
        valores = {}
        res['value'] = valores

        if not (self.payment_term and (self.amount_net or self.amount_total)):
            return res

        if not self.date_invoice:
            self.date_invoice = fields.Date.context_today(self)

        valor = self.amount_net or 0

        #
        # Para a compatibilidade com a chamada original (super), que usa
        # o decorator deprecado api.one, pegamos aqui sempre o 1º elemento
        # da lista que vai ser retornada
        #

        computations = self.payment_term.compute(
            valor, self.date_invoice)[0]

        self.duplicata_ids = False

        payment_ids = []
        for idx, item in enumerate(computations):
            payment = dict(
                numero=str(idx + 1),
                data_vencimento=item[0],
                valor=item[1],
            )
            payment_ids.append(payment)
        self.duplicata_ids = payment_ids

    @api.multi
    def _prepare_financial_move(self, lines):
        return {
            'date_document': self.date_invoice,
            'type': '2receive',
            'partner_id': self.partner_id.id,
            'doc_source_id': self._name + ',' + str(self.id),
            'bank_id': 1,
            'company_id': self.company_id and self.company_id.id,
            'currency_id': self.currency_id.id,
            'payment_term_id':
                self.payment_term and self.payment_term.id or False,
            # 'analytic_account_id':
            # 'payment_mode_id:
            'lines': [self._prepare_move_item(item) for item in lines],
            'account_id': self.fiscal_category_id.financial_account_id.id,
            'document_type_id':
                self.fiscal_category_id.financial_document_type_id.id,
        }

    @api.multi
    def action_financial_create(self, move_lines):
        # TODO: Refatorar este método utilizando o campo:
        # move_line_receivable_id
        to_financial = []
        for x, y, item in move_lines:
            account_id = self.env[
                'account.account'].browse(item.get('account_id', []))
            if account_id.type in ('payable', 'receivable'):
                item['user_type_id'] = account_id.user_type.id
                item['user_type'] = account_id.user_type.id
                to_financial.append(item)

        p = self._prepare_financial_move(to_financial)
        self.env['financial.move']._create_from_dict(p)

    @api.multi
    def invoice_validate(self):
        super(AccountInvoice, self).invoice_validate()
        for invoice in self:
            #
            #  Geração dos lançamentos financeiros
            #
            # financial_create = self.filtered(
            #     lambda invoice: invoice.revenue_expense)
            # financial_create.action_financial_create(move_lines_new)
            invoice.action_financial_create()

            # invoice.financial_ids.write({
            #     'document_number': invoice.name or
            #                        invoice.move_id.name or '/'})
            # invoice.financial_ids.action_confirm()

    def action_financial_create(self):
        """ Cria o lançamento financeiro do documento fiscal
        :return:
        """
        for documento in self:
            if documento.state not in 'open':
                continue

                # if documento.emissao == TIPO_EMISSAO_PROPRIA and \
                #     documento.entrada_saida == ENTRADA_SAIDA_ENTRADA:
                #     continue

                #
                # Temporariamente, apagamos todos os lançamentos anteriores
                #
                documento.financial_ids.unlink()

            for duplicata in documento.duplicata_ids:
                dados = duplicata.prepara_financial_move()
                financial_move = \
                    self.env['financial.move'].create(dados)
                financial_move.action_confirm()

    @api.one
    @api.depends('financial_ids.state')
    def _compute_reconciled(self):
        self.reconciled = self.test_paid()

    @api.multi
    def test_paid(self):
        line_ids = self.financial_ids
        if not line_ids:
            return False
        return all(line.state == 'paid' for line in line_ids)
