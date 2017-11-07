# -*- coding: utf-8 -*-
#
# Copyright 2016 Taŭga Tecnologia
#    Aristides Caldeira <aristides.caldeira@tauga.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from __future__ import division, print_function, unicode_literals

from odoo import api, fields, models


class AccountChartTemplate(models.Model):
    _inherit = 'account.chart.template'

    is_brazilian = fields.Boolean(
        string=u'Is a Brazilian chart_template?',
    )
    empresa_id = fields.Many2one(
        comodel_name='sped.empresa',
        string='Empresa',
    )
    transfer_account_id = fields.Many2one(
        required=False,
    )

    # @api.depends('company_id', 'currency_id')
    # def _compute_is_brazilian(self):
    #     for chart_template in self:
    #         if chart_template.company_id.country_id:
    #             if chart_template.company_id.country_id.id == \
    #                     self.env.ref('base.br').id:
    #                 chart_template.is_brazilian = True
    #
    #                 #
    #                 # Brazilian accounting, by law, must always be in BRL
    #                 #
    #                 chart_template.currency_id = self.env.ref('base.BRL').id
    #
    #                 if chart_template.company_id.empresa_id:
    #                     chart_template.empresa_id = \
    #                         chart_template.company_id.empresa_id.id
    #
    #                 continue
    #
    #         chart_template.is_brazilian = False

    @api.onchange('empresa_id')
    def _onchange_empresa_id(self):
        self.ensure_one()
        self.company_id = self.empresa_id.company_id

    @api.model
    def create(self, dados):
        if 'company_id' in dados and 'empresa_id' not in dados:
            company = self.env['res.company'].browse(dados['company_id'])

            if company.empresa_id:
                dados['empresa_id'] = company.empresa_id.id

        return super(AccountChartTemplate, self).create(dados)

    def write(self, dados):
        if 'company_id' in dados and 'empresa_id' not in dados:
            company = self.env['res.company'].browse(dados['company_id'])

            if company.empresa_id:
                dados['empresa_id'] = company.empresa_id.id

        return super(AccountChartTemplate, self).write(dados)

    def try_loading_for_current_company(self):
        self.ensure_one()

        if not self.is_brazilian:
            return super(AccountChartTemplate,
                         self).try_loading_for_current_company()

        company = self.env.user.company_id
        # If we don't have any chart of account on this company, install this
        # chart of account
        if not company.chart_template_id:
            wizard = self.env['wizard.multi.charts.accounts'].create({
                'company_id': self.env.user.company_id.id,
                'chart_template_id': self.id,
                'code_digits': self.code_digits,
                'transfer_account_id': self.transfer_account_id.id
                if self.transfer_account_id else False,
                'currency_id': self.currency_id.id,
                'bank_account_code_prefix': self.bank_account_code_prefix,
                'cash_account_code_prefix': self.cash_account_code_prefix,
            })
            wizard.onchange_chart_template_id()
            wizard.execute()

    @api.multi
    def _load_template(self, company, code_digits=None,
                       transfer_account_id=None,
                       account_ref=None, taxes_ref=None):
        self.ensure_one()

        if not self.is_brazilian:
            return super(AccountChartTemplate, self).\
                _load_template(company,
                               code_digits=code_digits,
                               transfer_account_id=transfer_account_id,
                               account_ref=account_ref, taxes_ref=taxes_ref)

        if account_ref is None:
            account_ref = {}
        if taxes_ref is None:
            taxes_ref = {}
        if not code_digits:
            code_digits = self.code_digits
        if not transfer_account_id:
            transfer_account_id = self.transfer_account_id

        # AccountTaxObj = self.env['account.tax']
        #
        # Generate taxes from templates.
        # generated_tax_res = self.tax_template_ids._generate_tax(company)
        # taxes_ref.update(generated_tax_res['tax_template_to_tax'])

        # Generating Accounts from templates.
        account_template_ref = self.generate_account(taxes_ref, account_ref,
                                                     code_digits, company)
        account_ref.update(account_template_ref)

        # writing account values after creation of accounts
        # if transfer_account_id:
        #     company.transfer_account_id = \
        #       account_template_ref[transfer_account_id.id]
        # for key, value in generated_tax_res['account_dict'].items():
        #     if value['refund_account_id'] or value['account_id']:
        #         AccountTaxObj.browse(key).write({
        #             'refund_account_id': account_ref.
        #               get(value['refund_account_id'], False),
        #             'account_id': account_ref.
        #             get(value['account_id'], False),
        #         })

        # # Create Journals - Only done for root chart template
        # if not self.parent_id:
        #     self.generate_journals(account_ref, company)

        # generate properties function
        self.generate_properties(account_ref, company)

        # Generate Fiscal Position , Fiscal Position Accounts
        # and Fiscal Position Taxes from templates
        # self.generate_fiscal_position(taxes_ref, account_ref, company)

        # # Generate account operation template templates
        # self.generate_account_reconcile_model(taxes_ref,
        # account_ref, company)

        return account_ref, taxes_ref

    @api.multi
    def generate_account(self, tax_template_ref, acc_template_ref,
                         code_digits, company):
        self.ensure_one()

        if not self.is_brazilian:
            return super(AccountChartTemplate, self).generate_account(
                tax_template_ref, acc_template_ref, code_digits, company)

        account_template_pool = self.env['account.account.template']
        account_template_ids = account_template_pool.search(
            [('nocreate', '=', False), ('chart_template_id', '=', self.id)],
            order='code'
        )

        for account_template in account_template_ids:
            dados = self._get_account_vals(company, account_template, '',
                                           tax_template_ref)

            if account_template.parent_id:
                print(account_template.code)
                dados['parent_id'] = \
                    acc_template_ref[account_template.parent_id.id]

            account = self.create_record_with_xmlid(company, account_template,
                                                    'account.account', dados)
            acc_template_ref[account_template.id] = account

        return acc_template_ref

    def _get_account_vals(self, company, account_template, code_acc,
                          tax_template_ref):
        self.ensure_one()

        if not self.is_brazilian:
            return super(AccountChartTemplate, self)._get_account_vals(
                company, account_template, code_acc, tax_template_ref)

        # tax_ids = []
        # for tax in account_template.tax_ids:
        #     tax_ids.append(tax_template_ref[tax.id])

        dados = {
            'name': account_template.name,
            'currency_id': self.env.ref('base.BRL').id,
            'code': account_template.code,
            'user_type_id': account_template.user_type_id.id
            if account_template.user_type_id else False,
            'reconcile': account_template.reconcile,
            'note': account_template.note,
            'company_id': company.id,
            'tipo': account_template.tipo,
            # 'tax_ids': [(6, 0, tax_ids)],
            # 'tag_ids': [(6, 0, [t.id for t in account_template.tag_ids])],
        }

        return dados
