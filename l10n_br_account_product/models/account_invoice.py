# -*- coding: utf-8 -*-
# Copyright (C) 2013  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import datetime

from openerp import models, fields, api, _, tools
from openerp.addons import decimal_precision as dp
from openerp.exceptions import (RedirectWarning,
                                ValidationError,
                                Warning as UserError)

from .l10n_br_account_product import (
    PRODUCT_FISCAL_TYPE,
    PRODUCT_FISCAL_TYPE_DEFAULT)
from .product import PRODUCT_ORIGIN
from openerp.addons.l10n_br_account_product.sped.nfe.validator import txt
from .l10n_br_account_product import EXIGIBILIDADE
from ..constantes import (
    CAMPO_DOCUMENTO_FISCAL,
    CAMPO_DOCUMENTO_FISCAL_ITEM,
    ACCOUNT_AUTOMATICO_PARTICIPANTE,
    ACCOUNT_AUTOMATICO_PRODUTO,
)
from openerp.addons.l10n_br_base.tools.misc import calc_price_ratio


FIELD_STATE = {'draft': [('readonly', False)]}


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'
    _order = 'date_hour_invoice DESC, internal_number DESC'

    @api.model
    def _amount_line_tax(self, line):
        value = 0.0
        price = line.price_unit
        qty = line.quantity
        for computed in line.invoice_line_tax_id.compute_all(
                price, qty, product=line.product_id,
                partner=line.partner_id,
                fiscal_position=line.fiscal_position)['taxes']:
            tax = self.env['account.tax'].browse(computed['id'])
            if not tax.tax_code_id.tax_discount:
                value += computed.get('amount', 0.0)
        return value

    @api.one
    @api.depends('invoice_line', 'tax_line.amount')
    def _compute_amount(self):
        self.icms_base = 0.0
        self.icms_base_other = 0.0
        self.icms_value = 0.0
        self.icms_st_base = 0.0
        self.icms_st_value = 0.0
        self.ipi_base = sum(line.ipi_base for line in self.invoice_line)
        self.ipi_base_other = sum(
            line.ipi_base_other for line in self.invoice_line)
        self.ipi_value = sum(line.ipi_value for line in self.invoice_line)
        self.pis_base = sum(line.pis_base for line in self.invoice_line)
        self.pis_value = sum(line.pis_value for line in self.invoice_line)
        self.cofins_base = sum(line.cofins_base for line in self.invoice_line)
        self.cofins_value = sum(
            line.cofins_value for line in self.invoice_line)
        self.ii_value = sum(line.ii_value for line in self.invoice_line)
        self.icms_fcp_value = sum(
            line.icms_fcp_value for line in self.invoice_line)
        self.icms_dest_value = sum(
            line.icms_dest_value for line in self.invoice_line)
        self.icms_origin_value = sum(
            line.icms_origin_value for line in self.invoice_line)
        self.amount_discount = sum(
            line.discount_value for line in self.invoice_line)
        self.amount_insurance = sum(
            line.insurance_value for line in self.invoice_line)
        self.amount_costs = sum(
            line.other_costs_value for line in self.invoice_line)
        self.amount_freight = sum(
            line.freight_value for line in self.invoice_line)
        self.amount_total_taxes = sum(
            line.total_taxes for line in self.invoice_line)
        self.amount_gross = sum(line.price_gross for line in self.invoice_line)
        self.amount_tax_discount = 0.0
        self.amount_untaxed = sum(
            line.price_subtotal for line in self.invoice_line)
        if self.tax_line:
            self.amount_tax = sum(tax.amount
                                  for tax in self.tax_line
                                  if not tax.tax_code_id.tax_discount)
        else:
            self.amount_tax = sum(self._amount_line_tax(line)
                                  for line in self.invoice_line)
        self.amount_total = self.amount_tax + self.amount_untaxed

        self.vr_custo_comercial = sum(
            line.vr_custo_comercial for line in self.invoice_line)
        self.vr_custo_estoque = sum(
            line.vr_custo_estoque for line in self.invoice_line)
        self.vr_operacao = sum(
            line.vr_operacao for line in self.invoice_line)

        for line in self.invoice_line:
            if line.icms_cst_id.code not in (
                    '101', '102', '201', '202', '300', '500'):
                self.icms_base += line.icms_base
                self.icms_base_other += line.icms_base_other
                self.icms_value += line.icms_value
            else:
                self.icms_base += 0.00
                self.icms_base_other += 0.00
                self.icms_value += 0.00
            if line.icms_cst_id.code in ('10', '30', '60', '90'):
                self.icms_st_base += line.icms_st_base
                self.icms_st_value += line.icms_st_value
            else:
                self.icms_st_base += 0.00
                self.icms_st_value += 0.00

    @api.model
    @api.returns('l10n_br_account.fiscal_category')
    def _default_fiscal_category(self):
        DEFAULT_FCATEGORY_PRODUCT = {
            'in_invoice': 'in_invoice_fiscal_category_id',
            'out_invoice': 'out_invoice_fiscal_category_id',
            'in_refund': 'in_refund_fiscal_category_id',
            'out_refund': 'out_refund_fiscal_category_id'
        }
        default_fo_category = {'product': DEFAULT_FCATEGORY_PRODUCT}
        invoice_type = self._context.get('type', 'out_invoice')
        invoice_fiscal_type = self._context.get('fiscal_type', 'product')
        company = self.env['res.company'].browse(self.env.user.company_id.id)
        return company[default_fo_category[invoice_fiscal_type][invoice_type]]

    @api.model
    def _default_fiscal_document(self):
        if self.env.context.get('fiscal_document_code'):
            company = self.env['res.company'].browse(
                self.env.user.company_id.id)
            return company.product_invoice_id

    @api.model
    def _default_nfe_version(self):
        if self.env.context.get('fiscal_document_code'):
            company = self.env['res.company'].browse(
                self.env.user.company_id.id)
            return company.nfe_version

    @api.model
    def _default_fiscal_document_serie(self):
        result = self.env['l10n_br_account.document.serie']
        if self.env.context.get('fiscal_document_code'):
            company = self.env['res.company'].browse(
                self.env.context.get('force_company') or
                self.env.user.company_id.id)
            fiscal_document_series = [doc_serie for doc_serie in
                                      company.document_serie_product_ids if
                                      doc_serie.fiscal_document_id.id ==
                                      company.product_invoice_id.id and
                                      doc_serie.active]
            if fiscal_document_series:
                result = fiscal_document_series[0]
        return result

    @api.model
    def _default_nfe_purpose(self):
        nfe_purpose_default = {
            'in_invoice': '1',
            'out_invoice': '1',
            'in_refund': '4',
            'out_refund': '4'
        }
        invoice_type = self.env.context.get('type', 'out_invoice')
        return nfe_purpose_default.get(invoice_type)

    @api.one
    @api.depends('invoice_line.cfop_id')
    def _compute_cfops(self):
        lines = self.env['l10n_br_account_product.cfop']
        for line in self.invoice_line:
            if line.cfop_id:
                lines |= line.cfop_id
        self.cfop_ids = (lines).sorted()

    @api.multi
    def _compute_financial_ids(self):
        for record in self:
            document_id = record._name + ',' + str(record.id)

            financials = record.env['financial.move'].search(
                [['doc_source_id', '=', document_id]])
            record.financial_ids = financials
            #
            # paid = all(finan.state == 'paid' for finan in financials)
            # if paid:
            #     record.financial_paid = paid

    @api.multi
    @api.depends('financial_ids.state')
    def _compute_financial_paid(self):
        for record in self.sudo():
            paid = False
            if record.financial_ids:
                paid = all(finan.state == 'paid' for
                           finan in record.financial_ids)
            record.financial_paid = paid

    @api.one
    @api.depends('financial_paid', 'account_id',
                 'move_id.line_id.account_id',
                 'move_id.line_id.reconcile_id')
    def _compute_reconciled(self):
        self.sudo()
        reconciled = self.test_paid() or self.financial_paid
        print ('%s: %s\n' % (self.id, reconciled))
        self.reconciled = reconciled

                # @api.multi
                # def financial_line_id_payment_get(self):
                #     if not self.id:
                #         return []
                #     query = """SELECT fm.id
                #                FROM financial_move fm
                #                WHERE fm.doc_source_id = %s
                #                AND fm.company_id = %s
                #     """
                #     document_id = self._name + ',' + str(self.id)
                #     self._cr.execute(query, (document_id, self.company_id.id))
                #     return [row[0] for row in self._cr.fetchall()]

                # @api.multi
                # def test_paid_financial(self):
                #     line_ids = self.financial_line_id_payment_get()
                #     if line_ids:
                #         lines = self.sudo().env['financial.move'].browse(line_ids)
                #         return all(line.state == 'paid' for line in lines)
                #     else:
                #         return False

    @api.multi
    @api.depends('invoice_line', 'tax_line.amount', 'issqn_wh', 'irrf_wh',
                 'inss_wh', 'csll_wh', 'pis_wh', 'cofins_wh')
    def _amount_all_service(self):
        for inv in self:
            inv.amount_services = sum(
                line.price_subtotal for line in inv.invoice_line
                if line.product_type == 'service')
            inv.issqn_base = sum(line.issqn_base for line in inv.invoice_line
                                 if line.product_type == 'service')
            inv.issqn_value = sum(
                line.issqn_value for line in inv.invoice_line
                if line.product_type == 'service')
            inv.service_pis_value = sum(
                line.pis_value for line in inv.invoice_line
                if line.product_type == 'service')
            inv.service_cofins_value = sum(
                line.cofins_value for line in inv.invoice_line
                if line.product_type == 'service')
            inv.csll_base = sum(line.csll_base for line in inv.invoice_line
                                if line.product_type == 'service')
            inv.csll_value = sum(line.csll_value for line in inv.invoice_line
                                 if line.product_type == 'service')
            inv.ir_base = sum(line.ir_base for line in inv.invoice_line
                              if line.product_type == 'service')
            inv.ir_value = sum(line.ir_value for line in inv.invoice_line
                               if line.product_type == 'service')
            inv.inss_base = sum(line.inss_base for line in inv.invoice_line
                                if line.product_type == 'service')
            inv.inss_value = sum(line.inss_value for line in inv.invoice_line
                                 if line.product_type == 'service')
            inv.issqn_value_wh = sum(line.issqn_wh_value for line
                                     in inv.invoice_line) \
                if inv.issqn_wh else 0.0
            inv.inss_value_wh = sum(line.inss_wh_value for line
                                     in inv.invoice_line) \
                if inv.inss_wh else 0.0
            inv.csll_value_wh = sum(line.csll_wh_value for line
                                     in inv.invoice_line) \
                if inv.csll_wh else 0.0
            inv.irrf_base_wh = sum(line.ir_base for line in inv.invoice_line
                              if line.product_type == 'service')
            inv.irrf_value_wh = sum(line.ir_wh_value for line
                                     in inv.invoice_line) \
                if inv.irrf_wh else 0.0
            inv.pis_value_wh = sum(line.pis_wh_value for line
                                     in inv.invoice_line) \
                if inv.pis_wh else 0.0
            inv.cofins_value_wh = sum(line.cofins_wh_value for line
                                     in inv.invoice_line) \
                if inv.cofins_wh else 0.0

            inv.amount_pis_cofins_csll = inv.service_cofins_value + \
                                         inv.service_pis_value + inv.csll_value
            inv.amount_total = inv.amount_tax + inv.amount_untaxed
            inv.amount_wh = (inv.issqn_value_wh + inv.pis_value_wh + inv.
                             cofins_value_wh + inv.csll_value_wh + inv.
                             irrf_value_wh + inv.inss_value_wh)

    @api.one
    def _set_irrf_wh(self):
        for line in self.invoice_line:
            line.write({
                'ir_wh_value': calc_price_ratio(
                    line.price_gross,
                    self.irrf_value_wh,
                    line.invoice_id.amount_total
                )
            })
        return True

    @api.one
    def _set_csll_wh(self):
        for line in self.invoice_line:
            line.write({
                'csll_wh_value': calc_price_ratio(
                    line.price_gross,
                    self.csll_value_wh,
                    line.invoice_id.amount_total
                )
            })
        return True

    @api.one
    def _set_inss_wh(self):
        for line in self.invoice_line:
            line.write({
                'inss_wh_value': calc_price_ratio(
                    line.price_gross,
                    self.inss_value_wh,
                    line.invoice_id.amount_total
                )
            })
        return True

    @api.one
    def _set_pis_wh(self):
        for line in self.invoice_line:
            line.write({
                'pis_wh_value': calc_price_ratio(
                    line.price_gross,
                    self.pis_value_wh,
                    line.invoice_id.amount_total
                )
            })
        return True

    @api.one
    def _set_cofins_wh(self):
        for line in self.invoice_line:
            line.write({
                'cofins_wh_value': calc_price_ratio(
                    line.price_gross,
                    self.cofins_value_wh,
                    line.invoice_id.amount_total
                )
            })
        return True

    @api.one
    def _set_issqn_wh(self):
        for line in self.invoice_line:
            line.write({
                'issqn_wh_value': calc_price_ratio(
                    line.price_gross,
                    self.issqn_value_wh,
                    line.invoice_id.amount_total
                )
            })
        return True

    @api.multi
    @api.depends('amount_total', 'amount_wh')
    def _amount_net(self):
        for inv in self:
            inv.amount_net = inv.amount_total - inv.amount_wh

    issuer = fields.Selection(
        [('0', u'Emissão própria'), ('1', 'Terceiros')],
        'Emitente',
        default='0',
        readonly=True,
        states={'draft': [('readonly', False)]}
    )
    # FIXME
    internal_number = fields.Char(
        'Invoice Number', size=32, readonly=True,
        states={'draft': [('readonly', False)]},
        help="""Unique number of the invoice, computed
            automatically when the invoice is created.""")
    type = fields.Selection(
        states={'draft': [('readonly', False)]}
    )
    serie_nfe = fields.Char(
        'Série NF', size=12, readonly=True, oldname='vendor_serie',
        states={'draft': [('readonly', False)]},
        help=u"Série do número da Nota Fiscal do Fornecedor")
    nfe_version = fields.Selection(
        [('1.10', '1.10'), ('2.00', '2.00'), ('3.10', '3.10')],
        u'Versão NFe', readonly=True, default=_default_nfe_version,
        states={'draft': [('readonly', False)]})
    date_hour_invoice = fields.Datetime(
        u'Data e hora de emissão', readonly=True,
        states={'draft': [('readonly', False)]},
        select=True, help="Deixe em branco para usar a data atual")
    ind_final = fields.Selection(
        [('0', u'Não'),
         ('1', u'Sim')],
        u'Consumidor final', readonly=True,
        related='fiscal_position.ind_final',
        states={'draft': [('readonly', False)]}, required=False,
        help=u'Indica operação com Consumidor final.')
    ind_pres = fields.Selection([
        ('0', u'Não se aplica'),
        ('1', u'Operação presencial'),
        ('2', u'Operação não presencial, pela Internet'),
        ('3', u'Operação não presencial, Teleatendimento'),
        ('4', u'NFC-e em operação com entrega em domicílio'),
        ('9', u'Operação não presencial, outros'),
    ], u'Tipo de operação', readonly=True,
        states={'draft': [('readonly', False)]}, required=False,
        help=u'Indicador de presença do comprador no\n'
             u'estabelecimento comercial no momento\n'
             u'da operação.', default='0')
    fiscal_document_id = fields.Many2one(
        'l10n_br_account.fiscal.document', 'Documento', readonly=True,
        states={'draft': [('readonly', False)]},
        default=_default_fiscal_document)
    fiscal_document_electronic = fields.Boolean(
        related='fiscal_document_id.electronic')
    document_serie_id = fields.Many2one(
        'l10n_br_account.document.serie', u'Série',
        domain="[('fiscal_document_id', '=', fiscal_document_id),\
        ('company_id','=',company_id)]", readonly=True,
        states={'draft': [('readonly', False)]},
        default=_default_fiscal_document_serie)
    fiscal_category_id = fields.Many2one(
        'l10n_br_account.fiscal.category', 'Categoria Fiscal',
        readonly=True,
        states={'draft': [('readonly', False)]},
        default=_default_fiscal_category,
    )
    date_in_out = fields.Datetime(
        u'Data de Entrada/Saida',
        readonly=True,
        states={
            'draft': [
                ('readonly',
                 False)]},
        select=True,
        copy=False,
        help="Deixe em branco para usar a data atual")
    partner_shipping_id = fields.Many2one(
        'res.partner', 'Delivery Address',
        readonly=True, required=True,
        states={'draft': [('readonly', False)]},
        help="Delivery address for current sales order.")
    fiscal_type = fields.Selection(
        PRODUCT_FISCAL_TYPE,
        'Tipo Fiscal',
        default=PRODUCT_FISCAL_TYPE_DEFAULT)
    partner_shipping_id = fields.Many2one(
        'res.partner', u'Endereço de Entrega', readonly=True,
        states={'draft': [('readonly', False)]},
        help="Shipping address for current sales order.")
    shipping_state_id = fields.Many2one(
        'res.country.state', 'Estado de Embarque')
    shipping_location = fields.Char('Local de Embarque', size=32)
    expedition_location = fields.Char('Local de Despacho', size=32)
    nfe_purpose = fields.Selection(
        [('1', 'Normal'),
         ('2', 'Complementar'),
         ('3', 'Ajuste'),
         ('4', u'Devolução de Mercadoria')],
        u'Finalidade da Emissão', readonly=True,
        states={'draft': [('readonly', False)]}, default=_default_nfe_purpose)
    nfe_access_key = fields.Char(
        'Chave de Acesso NFE', size=44,
        readonly=True, states={'draft': [('readonly', False)]}, copy=False)
    nfe_protocol_number = fields.Char(
        'Protocolo', size=15, readonly=True,
        copy=False, states={'draft': [('readonly', False)]})
    nfe_status = fields.Char('Status na Sefaz', size=44, readonly=True,
                             copy=False)
    nfe_date = fields.Datetime('Data do Status NFE', readonly=True,
                               copy=False)
    nfe_export_date = fields.Datetime(u'Exportação NFE', readonly=True)
    cfop_ids = fields.Many2many(
        'l10n_br_account_product.cfop', string='CFOP',
        copy=False, compute='_compute_cfops')
    fiscal_document_related_ids = fields.One2many(
        'l10n_br_account_product.document.related', 'invoice_id',
        'Fiscal Document Related', readonly=True,
        states={'draft': [('readonly', False)]})
    carrier_name = fields.Char('Nome Transportadora', size=32)
    vehicle_plate = fields.Char(u'Placa do Veículo', size=7)
    vehicle_state_id = fields.Many2one('res.country.state', 'UF da Placa')
    vehicle_l10n_br_city_id = fields.Many2one(
        'l10n_br_base.city',
        u'Município',
        domain="[('state_id', '=', vehicle_state_id)]")
    amount_untaxed = fields.Float(
        string='Untaxed',
        store=True,
        digits=dp.get_precision('Account'),
        compute='_compute_amount')
    amount_tax = fields.Float(
        string='Tax',
        store=True,
        digits=dp.get_precision('Account'),
        compute='_compute_amount')
    amount_total = fields.Float(
        string='Total',
        store=True,
        digits=dp.get_precision('Account'),
        compute='_compute_amount')
    amount_gross = fields.Float(
        string='Vlr. Bruto',
        store=True,
        digits=dp.get_precision('Account'),
        compute='_compute_amount',
        readonly=True)
    amount_discount = fields.Float(
        string='Desconto',
        store=True,
        digits=dp.get_precision('Account'),
        compute='_compute_amount')
    icms_base = fields.Float(
        string='Base ICMS',
        store=True,
        digits=dp.get_precision('Account'),
        compute='_compute_amount')
    icms_base_other = fields.Float(
        string='Base ICMS Outras',
        store=True,
        digits=dp.get_precision('Account'),
        compute='_compute_amount',
        readonly=True)
    icms_value = fields.Float(
        string='Valor ICMS', digits=dp.get_precision('Account'),
        compute='_compute_amount', store=True)
    icms_st_base = fields.Float(
        string='Base ICMS ST',
        store=True,
        digits=dp.get_precision('Account'),
        compute='_compute_amount')
    icms_st_value = fields.Float(
        string='Valor ICMS ST',
        store=True,
        digits=dp.get_precision('Account'),
        compute='_compute_amount')
    ipi_base = fields.Float(
        string='Base IPI', store=True, digits=dp.get_precision('Account'),
        compute='_compute_amount')
    ipi_base_other = fields.Float(
        string="Base IPI Outras", store=True,
        digits=dp.get_precision('Account'), compute='_compute_amount')
    ipi_value = fields.Float(
        string='Valor IPI', store=True,
        digits=dp.get_precision('Account'), compute='_compute_amount')
    pis_base = fields.Float(
        string='Base PIS', store=True,
        digits=dp.get_precision('Account'), compute='_compute_amount')
    pis_value = fields.Float(
        string='Valor PIS', store=True,
        digits=dp.get_precision('Account'), compute='_compute_amount')
    cofins_base = fields.Float(
        string='Base COFINS', store=True,
        digits=dp.get_precision('Account'), compute='_compute_amount')
    cofins_value = fields.Float(
        string='Valor COFINS', store=True,
        digits=dp.get_precision('Account'), compute='_compute_amount',
        readonly=True)
    ii_value = fields.Float(
        string='Valor II', store=True,
        digits=dp.get_precision('Account'), compute='_compute_amount',
        readonly=True)
    icms_fcp_value = fields.Float(
        string='Valor total do Fundo de Combate à Pobreza (FCP)', store=True,
        digits=dp.get_precision('Account'), compute='_compute_amount',
        readonly=True)
    icms_dest_value = fields.Float(
        string='Valor total do ICMS Interestadual para a UF de destino',
        store=True,
        digits=dp.get_precision('Account'), compute='_compute_amount',
        readonly=True)
    icms_origin_value = fields.Float(
        string='Valor total do ICMS Interestadual para a UF do remetente',
        store=True,
        digits=dp.get_precision('Account'), compute='_compute_amount',
        readonly=True)
    weight = fields.Float(
        string='Gross weight', states={'draft': [('readonly', False)]},
        help="The gross weight in Kg.", readonly=True)
    weight_net = fields.Float(
        'Net weight', help="The net weight in Kg.",
        readonly=True, states={'draft': [('readonly', False)]})
    number_of_packages = fields.Integer(
        'Volume', readonly=True, states={'draft': [('readonly', False)]})
    kind_of_packages = fields.Char(
        u'Espécie', size=60, readonly=True, states={
            'draft': [
                ('readonly', False)]})
    brand_of_packages = fields.Char(
        'Brand', size=60, readonly=True, states={
            'draft': [
                ('readonly', False)]})
    notation_of_packages = fields.Char(
        u'Numeração', size=60, readonly=True, states={
            'draft': [
                ('readonly', False)]})
    amount_insurance = fields.Float(
        string='Valor do Seguro', store=True,
        digits=dp.get_precision('Account'), compute='_compute_amount')
    amount_freight = fields.Float(
        string='Valor do Frete', store=True,
        digits=dp.get_precision('Account'), compute='_compute_amount')
    amount_costs = fields.Float(
        string='Outros Custos', store=True,
        digits=dp.get_precision('Account'), compute='_compute_amount')
    amount_total_taxes = fields.Float(
        string='Total de Tributos',
        store=True,
        digits=dp.get_precision('Account'),
        compute='_compute_amount')
    issqn_wh = fields.Boolean(
        u'Retém ISSQN', readonly=True, states=FIELD_STATE)
    issqn_value_wh = fields.Float(
        u'Valor da retenção do ISSQN', readonly=True,
        compute='_amount_all_service', states=FIELD_STATE,
        digits_compute=dp.get_precision('Account'), inverse=_set_issqn_wh)
    pis_wh = fields.Boolean(
        u'Retém PIS', readonly=True, states=FIELD_STATE)
    pis_value_wh = fields.Float(
        u'Valor da retenção do PIS', readonly=True,
        compute='_amount_all_service', states=FIELD_STATE,
        digits_compute=dp.get_precision('Account'), inverse=_set_pis_wh)
    cofins_wh = fields.Boolean(
        u'Retém COFINS', readonly=True, states=FIELD_STATE)
    cofins_value_wh = fields.Float(
        u'Valor da retenção do Cofins', readonly=True,
        compute='_amount_all_service', states=FIELD_STATE,
        digits_compute=dp.get_precision('Account'), inverse=_set_cofins_wh)
    csll_wh = fields.Boolean(
        u'Retém CSLL', readonly=True, states=FIELD_STATE)
    csll_value_wh = fields.Float(
        u'Valor da retenção de CSLL', readonly=True,
        compute='_amount_all_service', states=FIELD_STATE,
        digits_compute=dp.get_precision('Account'), inverse=_set_csll_wh)
    irrf_wh = fields.Boolean(
        u'Retém IRRF', readonly=True, states=FIELD_STATE)
    irrf_base_wh = fields.Float(
        u'Base de calculo retenção do IRRF', readonly=True,
        compute='_amount_all_service', states=FIELD_STATE,
        digits_compute=dp.get_precision('Account'))
    irrf_value_wh = fields.Float(
        u'Valor da retenção de IRRF', readonly=True,
        compute='_amount_all_service', states=FIELD_STATE,
        digits_compute=dp.get_precision('Account'), inverse=_set_irrf_wh
    )
    inss_wh = fields.Boolean(
        u'Retém INSS', readonly=True, states=FIELD_STATE)
    inss_base_wh = fields.Float(
        u'Base de Cálculo da Retenção da Previdência Social', readonly=True,
        states=FIELD_STATE, digits_compute=dp.get_precision('Account'),
        compute='_amount_all_service')
    inss_value_wh = fields.Float(
        u'Valor da Retenção da Previdência Social ', readonly=True,
        states=FIELD_STATE, digits_compute=dp.get_precision('Account'),
        compute='_amount_all_service', inverse=_set_inss_wh)
    csll_base = fields.Float(
        string=u'Base CSLL', compute='_amount_all_service',
        digits_compute=dp.get_precision('Account'), store=True)
    csll_value = fields.Float(
        string=u'Valor CSLL', compute='_amount_all_service',
        digits_compute=dp.get_precision('Account'), store=True)
    ir_base = fields.Float(
        string=u'Base IR', compute='_amount_all_service',
        digits_compute=dp.get_precision('Account'), store=True)
    ir_value = fields.Float(
        string=u'Valor IR', compute='_amount_all_service',
        digits_compute=dp.get_precision('Account'), store=True)
    issqn_base = fields.Float(
        string=u'Base de Cálculo do ISSQN', compute='_amount_all_service',
        digits_compute=dp.get_precision('Account'), store=True)
    issqn_value = fields.Float(
        string=u'Valor do ISSQN', compute='_amount_all_service',
        digits_compute=dp.get_precision('Account'), store=True)
    inss_base = fields.Float(
        string=u'Valor do INSS', compute='_amount_all_service',
        digits_compute=dp.get_precision('Account'), store=True)
    inss_value = fields.Float(
        string=u'Valor do INSS', compute='_amount_all_service',
        digits_compute=dp.get_precision('Account'), store=True)
    service_pis_value = fields.Float(
        string=u'Valor do Pis sobre Serviços', compute='_amount_all_service',
        digits_compute=dp.get_precision('Account'), store=True)
    service_cofins_value = fields.Float(
        string=u'Valor do Cofins sobre Serviços',
        compute='_amount_all_service',
        store=True, digits_compute=dp.get_precision('Account'))
    amount_services = fields.Float(
        string=u'Total dos serviços',
        compute='_amount_all_service',
        store=True,
        digits_compute=dp.get_precision('Account'))
    amount_pis_cofins_csll = fields.Float(
        string=u'PIS/CONFINS/CSLL',
        compute='_amount_all_service',
        store=True,
        digits_compute=dp.get_precision('Account'))
    amount_wh = fields.Float(
        string=u'Total de retenção',
        compute='_amount_all_service',
        store=True,
        digits_compute=dp.get_precision('Account'))
    amount_net = fields.Float(
        string=u'Valor Fatura', compute='_amount_net',
        digits_compute=dp.get_precision('Account'),
        help=u'Quanto o parceiro deve pagar:\n'
             u'Valor da nota fiscal\n'
             u'- retenções\n'
    )
    vr_custo_comercial = fields.Float(
        string=u'Valor custo comercial',
        store=True,
        compute='_compute_amount',
        digits=dp.get_precision('Account'),
        help=u'Valor dos produtos\n'
             u' + impostos pagos\n'
             u' - impostos creditados\n'
             u'Determinados durante a contabilização da compra'
    )
    vr_custo_estoque = fields.Float(
        string=u'Valor custo estoque',
        store=True,
        compute='_compute_amount',
        digits=dp.get_precision('Account'),
        help=u'Custo do produto aplicado nas operações de vendas:\n'
             u' - calculado com base no metodo de formação de custo'
             u'configurado no cadastro do produto'
    )
    vr_operacao = fields.Float(
        string=u'Valor Operação',
        store=True,
        compute='_compute_amount',
        digits=dp.get_precision('Account'),
        help=u'Valor da operação = '
             u'valor dos produtos\n'
             u' + frete\n'
             u' + outros custos\n'
             u' + seguro\n'
             u' - desconto'
    )
    financial_ids = fields.One2many(
        comodel_name='financial.move',
        compute='_compute_financial_ids',
        string=u'Financial Items',
        readonly=True,
        copy=False
    )
    account_move_template_id = fields.Many2one(
        comodel_name='sped.account.move.template',
        string='Modelo de partida dobrada',
    )
    duplicata_ids = fields.One2many(
        comodel_name='sped.documento.duplicata',
        inverse_name='invoice_id',
        string=u'Duplicatas',
    )
    financial_paid = fields.Boolean(
        string='Duplicatas pagas',
        compute='_compute_financial_paid',
        store=True,
        copy=False,
    )

    @api.one
    @api.constrains('number')
    def _check_invoice_number(self):
        domain = []
        if self.number:
            fiscal_document = self.fiscal_document_id and\
                self.fiscal_document_id.id or False
            domain.extend([('internal_number', '=', self.number),
                           ('fiscal_type', '=', self.fiscal_type),
                           ('fiscal_document_id', '=', fiscal_document)
                           ])
            if self.issuer == '0':
                domain.extend([
                    ('company_id', '=', self.company_id.id),
                    ('internal_number', '=', self.number),
                    ('fiscal_document_id', '=', self.fiscal_document_id.id),
                    ('issuer', '=', '0')])
            else:
                domain.extend([
                    ('partner_id', '=', self.partner_id.id),
                    ('serie_nfe', '=', self.serie_nfe),
                    ('issuer', '=', '1')])

            invoices = self.env['account.invoice'].search(domain)
            if len(invoices) > 1:
                raise UserError(u'Não é possível registrar documentos\
                              fiscais com números repetidos.')

    def _fiscal_position_map(self, result, **kwargs):
        ctx = dict(self._context)
        ctx.update({'use_domain': ('use_invoice', '=', True)})
        if ctx.get('fiscal_category_id'):
            kwargs['fiscal_category_id'] = ctx.get('fiscal_category_id')

        if not kwargs.get('fiscal_category_id'):
            return result

        company = self.env['res.company'].browse(kwargs.get('company_id'))

        fcategory = self.env['l10n_br_account.fiscal.category'].browse(
            kwargs.get('fiscal_category_id'))
        result['value']['journal_id'] = fcategory.property_journal.id
        if not result['value'].get('journal_id', False):
            raise UserError(
                _('Nenhum Diário !'),
                _("Categoria fiscal: '%s', não tem um diário contábil para a \
                empresa %s") % (fcategory.name, company.name))
        return self.env['account.fiscal.position.rule'].with_context(
            ctx).apply_fiscal_mapping(result, **kwargs)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form',
                        toolbar=False, submenu=False):
        context = self.env.context
        fiscal_document_code = context.get('fiscal_document_code')
        active_id = context.get('active_id')
        nfe_form = 'l10n_br_account_product.l10n_br_account_product_nfe_form'
        nfe_tree = 'l10n_br_account_product.l10n_br_account_product_nfe_tree'
        nfe_views = {'form': nfe_form, 'tree': nfe_tree}

        if context.get('active_model') == 'account.invoice' and \
                active_id and not fiscal_document_code:
            invoice = self.browse(active_id)
            fiscal_document_code = invoice.fiscal_document_id.code

        if nfe_views.get(view_type) and fiscal_document_code == u'55':
            view_id = self.env.ref(nfe_views.get(view_type)).id

        return super(AccountInvoice, self).fields_view_get(
            view_id=view_id, view_type=view_type,
            toolbar=toolbar, submenu=submenu)

    # TODO Imaginar em não apagar o internal number para nao ter a necessidade
    # de voltar a numeracão
    @api.multi
    def action_cancel_draft(self):
        result = super(AccountInvoice, self).action_cancel_draft()
        self.write({
            'internal_number': False,
            'nfe_access_key': False,
            'nfe_status': False,
            'nfe_date': False,
            'nfe_export_date': False})
        return result

    def nfe_check(self, cr, uid, ids, context=None):
        if context.get('fiscal_document_code', '') == '55':
            result = txt.validate(cr, uid, ids, context)
            return result

    @api.multi
    def action_number(self):
        # TODO: not correct fix but required a fresh values before reading it.
        self.write({})

        for invoice in self:
            if invoice.issuer == '0':
                sequence_obj = self.env['ir.sequence']
                sequence = sequence_obj.browse(
                    invoice.document_serie_id.internal_sequence_id.id)
                invalid_number = self.env[
                    'l10n_br_account.invoice.invalid.number'].search(
                    [('number_start', '<=', sequence.number_next),
                     ('number_end', '>=', sequence.number_next),
                     ('document_serie_id', '=', invoice.document_serie_id.id),
                     ('state', '=', 'done')])

                if invalid_number:
                    raise UserError(
                        _(u'Número Inválido !'),
                        _("O número: %s da série: %s, esta inutilizado") % (
                            sequence.number_next,
                            invoice.document_serie_id.name))

                seq_number = sequence_obj.get_id(
                    invoice.document_serie_id.internal_sequence_id.id)
                date_time_invoice = (invoice.date_hour_invoice or
                                     fields.datetime.now())
                date_in_out = invoice.date_in_out or fields.datetime.now()
                self.write(
                    {'internal_number': seq_number,
                     'serie_nfe': invoice.document_serie_id.code,
                     'number': seq_number,
                     'date_hour_invoice': date_time_invoice,
                     'date_in_out': date_in_out,
                     'ref': seq_number,
                     }
                )
        return True

    @api.onchange('type')
    def onchange_type(self):
        ctx = dict(self.env.context)
        ctx.update({'type': self.type})
        self.fiscal_category_id = (
            self.with_context(ctx)._default_fiscal_category()
        )

    @api.onchange('fiscal_document_id')
    def onchange_fiscal_document_id(self):
        if self.fiscal_type == 'product':
            if self.issuer == '0':
                series = [doc_serie for doc_serie in
                          self.company_id.document_serie_product_ids if
                          doc_serie.fiscal_document_id.id ==
                          self.fiscal_document_id.id and doc_serie.active]

                if not series:
                    action = self.env.ref(
                        'l10n_br_account.'
                        'action_l10n_br_account_document_serie_form')
                    msg = _(u'Você deve ser uma série de documento fiscal'
                            u'para este documento fiscal.')
                    raise RedirectWarning(
                        msg, action.id, _(u'Criar uma nova série'))
                self.document_serie_id = series[0]

    @api.onchange('fiscal_category_id', 'fiscal_position')
    def onchange_fiscal(self):
        if self.company_id and self.partner_id and self.fiscal_category_id:
            result = {'value': {}}
            kwargs = {
                'company_id': self.company_id.id,
                'partner_id': self.partner_id.id,
                'partner_invoice_id': self.partner_id.id,
                'fiscal_category_id': self.fiscal_category_id.id,
                'context': self.env.context
            }
            result = self._fiscal_position_map(result, **kwargs)
            self.update(result['value'])

    @api.multi
    def action_date_assign(self):
        for inv in self:
            if not inv.date_hour_invoice:
                date_hour_invoice = fields.Datetime.context_timestamp(
                    self, datetime.datetime.now())
            else:
                if inv.issuer == '1':
                    date_move = inv.date_in_out
                else:
                    date_move = inv.date_hour_invoice
                date_hour_invoice = fields.Datetime.context_timestamp(
                    self, datetime.datetime.strptime(
                        date_move, tools.DEFAULT_SERVER_DATETIME_FORMAT
                    )
                )
            date_invoice = date_hour_invoice.strftime(
                tools.DEFAULT_SERVER_DATE_FORMAT)
            res = self.onchange_payment_term_date_invoice(
                inv.payment_term.id, date_invoice)
            if res and res['value']:
                res['value'].update({
                    'date_invoice': date_invoice
                })
                date_time_now = fields.datetime.now()
                if not inv.date_hour_invoice:
                    res['value'].update({'date_hour_invoice': date_time_now})
                if not inv.date_in_out:
                    res['value'].update({'date_in_out': date_time_now})
                inv.write(res['value'])
        return True

    @api.multi
    def open_fiscal_document(self):
        """return action to open NFe form"""
        result = super(AccountInvoice, self).open_fiscal_document()
        result['name'] = _('NF-e')
        return result

    def withholding_map(self, cr, uid, **kwargs):
        result = {}
        obj_partner = self.pool.get('res.partner').browse(
            cr, uid, kwargs.get('partner_id', False))
        obj_company = self.pool.get('res.company').browse(
            cr, uid, kwargs.get('company_id', False))

        result['issqn_wh'] = obj_company.issqn_wh or obj_partner.\
            partner_fiscal_type_id.issqn_wh
        result['inss_wh'] = obj_company.inss_wh or obj_partner.\
            partner_fiscal_type_id.inss_wh
        result['pis_wh'] = obj_company.pis_wh or obj_partner.\
            partner_fiscal_type_id.pis_wh
        result['cofins_wh'] = obj_company.cofins_wh or obj_partner.\
            partner_fiscal_type_id.cofins_wh
        result['csll_wh'] = obj_company.csll_wh or obj_partner.\
            partner_fiscal_type_id.csll_wh
        result['irrf_wh'] = obj_company.irrf_wh or obj_partner.\
            partner_fiscal_type_id.irrf_wh

        return result

    def onchange_partner_id(self, cr, uid, ids, type, partner_id,
                            date_invoice=False, payment_term=False,
                            partner_bank_id=False, company_id=False,
                            fiscal_category_id=False):

        result = super(AccountInvoice, self).onchange_partner_id(
            cr, uid, ids, type, partner_id, date_invoice, payment_term,
            partner_bank_id, company_id, fiscal_category_id)

        result['value'].update(self.withholding_map(
            cr, uid, partner_id=partner_id, company_id=company_id))

        return result

    @api.multi
    def _prepare_move_item(self, item):
        return {
            'document_number': '/',
            'date_maturity': item['date_maturity'],
            'amount_document': item['debit'] or item['credit'],
            'account_type_id': item['user_type_id'],
        }

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
    def gera_account_move_line(self, line_ids, template_nao_contabilizados):
        campos_jah_contabilizados = []

        if self.type in ('in_invoice', 'in_refund'):
            ref = self.reference
        else:
            ref = self.number

        for template_item in template_nao_contabilizados:
        
            if not getattr(self, template_item.campo, False):
                continue

            if template_item.campo in campos_jah_contabilizados:
                #
                # O que fazemos quando dois templates tentarem o contabilizar
                # o mesmo campo?
                #
                continue

            #
            # Nas notas de entrada por compra ou devolução de venda, se
            # não se vai aproveitar o crédito do imposto, ele não é
            # contabilizado à parte
            #
            if self.type in ('in_invoice', 'out_refund'):
                if (template_item.campo in
                        ('icms_value', 'vr_icms_sn') and
                        not self.credita_icms):
                    continue
                elif template_item.campo == 'icms_st_value' and \
                        not self.credita_icms_st:
                    continue
                elif template_item.campo == 'ipi_value' and \
                        not self.credita_ipi:
                    continue
                elif template_item.campo in (
                        'pis_value', 'cofins_value') and \
                        not self.credita_pis_cofins:
                    continue

            valor = getattr(self, template_item.campo, 0)

            if not valor:
                continue

            account_debito = None
            if template_item.account_debito_id:
                account_debito = template_item.account_debito_id
            elif template_item.account_automatico_debito == ACCOUNT_AUTOMATICO_PARTICIPANTE:
                partner = self.partner_id
                if self.type in ('out_invoice', 'out_refund'):
                    if partner.property_account_receivable:
                        account_debito = \
                            partner.property_account_receivable
                    else:
                        raise UserError(
                            u'Conta de Recebimento não '
                            u'selecionada no parceiro.'
                        )
                elif self.type in ('in_invoice', 'in_refund'):
                    if partner.property_account_payable:
                        account_debito = partner.property_account_payable
                    else:
                        raise UserError(
                            u'Conta de Pagamento não selecionada no parceiro.'
                        )

            if account_debito is not None:
                dados = {
                    # 'move_id': account_move.id,
                    # 'sped_documento_item_id': self.id,
                    'account_id': account_debito.id,
                    'name': ref or '/',
                    'narration': template_item.campo,
                    'debit': valor,
                    # 'currency_id': self.currency_id.id,
                }
                line_ids.append((0, 0, dados))

            account_credito = None
            if template_item.account_credito_id:
                account_credito = template_item.account_credito_id
            elif template_item.account_automatico_credito == ACCOUNT_AUTOMATICO_PARTICIPANTE:
                partner = self.partner_id
                if self.type in ('out_invoice', 'out_refund'):
                    if partner.property_account_receivable:
                        account_credito = \
                            partner.property_account_receivable
                    else:
                        raise UserError(
                            u'Conta de Pagamento não selecionada no parceiro.'
                        )
                elif self.type in ('in_invoice', 'in_refund'):
                    if partner.property_account_payable:
                        account_credito = partner.property_account_payable
                    else:
                        raise UserError(
                            u'Conta de Pagamento não selecionada no parceiro.'
                        )

            if account_credito is not None:
                dados = {
                    'account_id': account_credito.id,
                    # 'move_id': account_move.id,
                    # 'sped_documento_item_id': self.id,
                    'name': ref or '/',
                    'narration': template_item.campo,
                    'credit': valor,
                    # 'currency_id': self.currency_id.id,
                }
                line_ids.append((0, 0, dados))

            campos_jah_contabilizados.append(template_item.campo)

    @api.multi
    def action_move_create(self):

        account_invoice_tax = self.env['account.invoice.tax']
        account_move = self.env['account.move']
        sped_account_move_template = self.env['sped.account.move.template']

        for inv in self:
            if not inv.journal_id.sequence_id:
                raise ValidationError(_('Error!'), _(
                    'Please define sequence on the journal related to this invoice.'))
            if not inv.invoice_line:
                raise ValidationError(_('No Invoice Lines!'), _(
                    'Please create some invoice lines.'))
            if inv.move_id:
                continue

            ctx = dict(self._context, lang=inv.partner_id.lang)

            company_currency = inv.company_id.currency_id
            if not inv.date_invoice:
                # FORWARD-PORT UP TO SAAS-6
                if inv.currency_id != company_currency and inv.tax_line:
                    raise ValidationError(
                        _('Warning!'),
                        _('No invoice date!'
                            '\nThe invoice currency is not the same than the '
                          'company currency.'
                            ' An invoice date is required to determine '
                          'the exchange rate to apply. Do not forget to update'
                          ' the taxes!'
                        )
                    )
                inv.with_context(ctx).write(
                    {'date_invoice': fields.Date.context_today(self)})
            date_invoice = inv.date_invoice

            # create the analytical lines, one move line per invoice line
            iml = inv._get_analytic_lines()
            # check if taxes are all computed
            compute_taxes = account_invoice_tax.compute(
                inv.with_context(lang=inv.partner_id.lang))
            inv.check_tax_lines(compute_taxes)

            # I disabled the check_total feature
            if self.env.user.has_group(
                    'account.group_supplier_inv_check_total'):
                if (inv.type in ('in_invoice', 'in_refund') and
                        abs(inv.check_total - inv.amount_total) >=
                        (inv.currency_id.rounding / 2.0)):
                    raise ValidationError(_('Bad Total!'), _(
                        'Please verify the price of the invoice!\nThe encoded'
                        ' total does not match the computed total.'))

            # Force recomputation of tax_amount, since the rate potentially changed between creation
            # and validation of the invoice
            inv._recompute_tax_amount()

            if inv.type in ('in_invoice', 'in_refund'):
                ref = inv.reference
            else:
                ref = inv.number

            diff_currency = inv.currency_id != company_currency
            # create one move line for the total and possibly adjust the other lines amount
            total, total_currency, iml = inv.with_context(
                ctx).compute_invoice_totals(company_currency, ref, iml)

            name = inv.supplier_invoice_number or inv.name or '/'

            date = date_invoice

            part = self.env['res.partner']._find_accounting_partner(
                inv.partner_id)

            line_id = []

            move_vals = {
                'ref': inv.internal_number or inv.name,
                'line_id': line_id,
                'journal_id': inv.journal_id.id,
                'partner_id': inv.partner_id.id,
                'date': inv.date_invoice,
                # 'date': inv.date_in_out,
                'company_id': inv.company_id.id,
                'narration': inv.comment,
                'name': inv.internal_number,
            }

            template_nao_contabilizados = set()
            #
            # Contabiliza as linhas e retorna os templates não contabilizados
            #
            for invoice_line in inv.invoice_line:
                move_template = invoice_line.account_move_template_id
                invoice_line.gera_account_move_line(
                    line_id, template_nao_contabilizados, move_template)

            #import ipdb; ipdb.set_trace();
            #
            # Contabiliza os campos do cabeçalho do documento
            #
            inv.gera_account_move_line(
                line_id, template_nao_contabilizados
            )

            #
            # Agrupa os laçamentos contábeis
            #

            # line = inv.group_lines(iml, line)

            journal = inv.journal_id.with_context(ctx)
            if journal.centralisation:
                raise ValidationError(
                    _('User Error!'),
                    _('You cannot create an invoice on a centralized journal.'
                      ' Uncheck the centralized counterpart box in the related'
                      ' journal from the configuration menu.'))

            # line = inv.finalize_invoice_move_lines(line_id)

            ctx['company_id'] = inv.company_id.id
            period = inv.period_id
            # if not period:
            #     period = period.with_context(ctx).find(date_invoice)[:1]
            # if period:
            #     move_vals['period_id'] = period.id
            #     for i in line:
            #         i[2]['period_id'] = period.id

            ctx['invoice'] = inv
            ctx_nolang = ctx.copy()
            ctx_nolang.pop('lang', None)

            move = account_move.with_context(ctx_nolang).create(move_vals)

            # make the invoice point to that move
            vals = {
                'move_id': move.id,
                'period_id': period.id,
                'move_name': move.name,
            }
            inv.with_context(ctx).write(vals)
            # Pass invoice in context in method post: used if you want to
            # get the same
            # account move reference when creating the same invoice after
            #  a cancelled one:
            # move.post()

        #
        # Chamamos o action_move_create para manter a chamadas de outros
        # módulos, mesmo que no core a criação do lançamento seja ignorada.
        #
        super(AccountInvoice, self).action_move_create()

    # @api.multi
    # def finalize_invoice_move_lines(self, move_lines):
    #     move_lines = super(AccountInvoice, self).finalize_invoice_move_lines(
    #         move_lines)
    #
    #     # What we do here? IMPORTANT
    #     # We make a copy of the retention tax and calculate the new total
    #     # in the payment lines
    #     value_to_debit = 0.0
    #     move_lines_new = []
    #     move_lines_tax = [move for move in move_lines
    #                       if not move[2]['product_id'] and
    #                       not move[2]['date_maturity']]
    #     move_lines_payment = [move for move in move_lines
    #                           if not move[2]['product_id'] and
    #                           move[2]['date_maturity']]
    #     move_lines_products = [move for move in move_lines
    #                            if move[2]['product_id'] and
    #                            not move[2]['date_maturity']]
    #
    #     def invert_credit_debit(move, value_to_debit):
    #         credit = move[2]['credit']
    #         debit = move[2]['debit']
    #         value_to_debit += move[2]['credit'] or move[2]['debit']
    #         move[2]['credit'] = debit
    #         move[2]['debit'] = credit
    #         return value_to_debit
    #
    #     for move in move_lines_tax:
    #         move_lines_new.append(move)
    #
    #         tax_code = self.env['account.tax.code'].browse(
    #             move[2]['tax_code_id'])
    #
    #         if tax_code.domain == 'retissqn' and self.issqn_wh:
    #             value_to_debit = invert_credit_debit(move, value_to_debit)
    #
    #         if tax_code.domain == 'retpis' and self.pis_wh:
    #             value_to_debit = invert_credit_debit(move, value_to_debit)
    #
    #         if tax_code.domain == 'retcofins' and self.cofins_wh:
    #             value_to_debit = invert_credit_debit(move, value_to_debit)
    #
    #         if tax_code.domain == 'retinss' and self.inss_wh:
    #             value_to_debit = invert_credit_debit(move, value_to_debit)
    #
    #         if tax_code.domain == 'retcsll' and self.csll_wh:
    #             value_to_debit = invert_credit_debit(move, value_to_debit)
    #
    #         if tax_code.domain == 'retir' and self.irrf_wh:
    #             value_to_debit = invert_credit_debit(move, value_to_debit)
    #
    #     move_lines_new.extend(move_lines_payment)
    #     move_lines_new.extend(move_lines_products)
    #
    #     if value_to_debit > 0.0:
    #         value_item = value_to_debit / float(len(move_lines_payment))
    #         for move in move_lines_payment:
    #             if move[2]['debit']:
    #                 move[2]['debit'] -= value_item
    #             elif move[2]['credit']:
    #                 move[2]['credit'] -= value_item
    #         for move in move_lines_products:
    #             if move[2]['debit']:
    #                 move[2]['debit'] += value_item
    #             elif move[2]['credit']:
    #                 move[2]['credit'] += value_item
    #
    #     return move_lines_new

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

    @api.model
    def create(self, vals):
        res = super(AccountInvoice, self).create(vals)
        if res.payment_term and not res.duplicata_ids:
            res.onchange_duplicatas()
        return res


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    @api.one
    @api.depends('price_unit', 'discount', 'invoice_line_tax_id', 'quantity',
                 'product_id', 'invoice_id.partner_id', 'freight_value',
                 'insurance_value', 'other_costs_value',
                 'invoice_id.currency_id')
    def _compute_price(self):
        price = self.price_unit * (1 - (self.discount or 0.0) / 100.0)
        taxes = self.invoice_line_tax_id.compute_all(
            price, self.quantity, product=self.product_id,
            partner=self.invoice_id.partner_id,
            fiscal_position=self.fiscal_position,
            insurance_value=self.insurance_value,
            freight_value=self.freight_value,
            other_costs_value=self.other_costs_value)
        self.price_tax_discount = 0.0
        self.price_subtotal = 0.0
        self.price_gross = 0.0
        self.discount_value = 0.0
        self.vr_custo_comercial = 0.00  # TODO: Não implementado
        self.vr_custo_estoque = 0.0  # TODO: Não implementado
        self.vr_operacao = 0.00

        if self.invoice_id:
            self.price_tax_discount = self.invoice_id.currency_id.round(
                taxes['total'] - taxes['total_tax_discount'])
            self.price_subtotal = self.invoice_id.currency_id.round(
                taxes['total'])
            self.price_gross = self.invoice_id.currency_id.round(
                self.price_unit * self.quantity)
            self.discount_value = self.invoice_id.currency_id.round(
                self.price_gross - taxes['total'])

            self.vr_operacao = (
                self.price_subtotal +
                self.insurance_value +
                self.freight_value +
                self.other_costs_value -
                self.discount_value
            )
            amount_tax = 0.0
            for computed in taxes['taxes']:
                tax = self.env['account.tax'].browse(computed['id'])
                if not tax.tax_code_id.tax_discount:
                    amount_tax += computed.get('amount', 0.0)
            self.price_total = self.price_subtotal + amount_tax

    @api.multi
    @api.depends('fiscal_category_id')
    def _compute_move_template(self):
        for record in self:
            record.account_move_template_id = \
                record.fiscal_category_id.account_move_template_id

    code = fields.Char(
        u'Código do Produto', size=60)
    date_invoice = fields.Datetime(
        'Invoice Date', readonly=True, states={'draft': [('readonly', False)]},
        select=True, help="Keep empty to use the current date")
    fiscal_category_id = fields.Many2one(
        'l10n_br_account.fiscal.category', 'Categoria Fiscal')
    fiscal_position = fields.Many2one(
        'account.fiscal.position', u'Posição Fiscal',
    )
    cfop_id = fields.Many2one('l10n_br_account_product.cfop', 'CFOP')
    fiscal_classification_id = fields.Many2one(
        'account.product.fiscal.classification', u'Classificação Fiscal')
    cest_id = fields.Many2one(
        comodel_name='l10n_br_account_product.cest',
        string=u'CEST'
    )
    fci = fields.Char('FCI do Produto', size=36)
    import_declaration_ids = fields.One2many(
        'l10n_br_account_product.import.declaration',
        'invoice_line_id', u'Declaração de Importação')
    product_type = fields.Selection(
        [('product', 'Produto'), ('service', u'Serviço')],
        'Tipo do Produto', required=True, default='product')
    discount_value = fields.Float(
        string='Vlr. desconto', store=True, compute='_compute_price',
        digits=dp.get_precision('Account'))
    price_gross = fields.Float(
        string='Vlr. Bruto', store=True, compute='_compute_price',
        digits=dp.get_precision('Account'))
    price_total = fields.Float(
        string='Vlr. Total', store=True, compute='_compute_price',
        digits=dp.get_precision('Account'))
    price_tax_discount = fields.Float(
        string='Vlr. s/ Impostos', store=True, compute='_compute_price',
        digits=dp.get_precision('Account'))
    total_taxes = fields.Float(
        string='Total de Tributos', requeried=True, default=0.00,
        digits=dp.get_precision('Account'))
    icms_manual = fields.Boolean('ICMS Manual?', default=False)
    icms_origin = fields.Selection(PRODUCT_ORIGIN, 'Origem', default='0')
    icms_base_type = fields.Selection(
        [('0', 'Margem Valor Agregado (%)'), ('1', 'Pauta (valor)'),
         ('2', u'Preço Tabelado Máximo (valor)'),
         ('3', u'Valor da Operação')],
        'Tipo Base ICMS', required=True, default='0')
    icms_base = fields.Float('Base ICMS', required=True,
                             digits=dp.get_precision('Account'), default=0.00)
    icms_base_other = fields.Float(
        'Base ICMS Outras', required=True,
        digits=dp.get_precision('Account'), default=0.00)
    icms_value = fields.Float(
        'Valor ICMS', required=True,
        digits=dp.get_precision('Account'), default=0.00)
    icms_percent = fields.Float(
        'Perc ICMS', digits=dp.get_precision('Discount'), default=0.00)
    icms_percent_reduction = fields.Float(
        u'Perc Redução de Base ICMS', digits=dp.get_precision('Discount'),
        default=0.00)
    icms_st_base_type = fields.Selection(
        [('0', u'Preço tabelado ou máximo  sugerido'),
         ('1', 'Lista Negativa (valor)'),
         ('2', 'Lista Positiva (valor)'), ('3', 'Lista Neutra (valor)'),
         ('4', 'Margem Valor Agregado (%)'), ('5', 'Pauta (valor)')],
        'Tipo Base ICMS ST', required=True, default='4')
    icms_st_value = fields.Float(
        'Valor ICMS ST', required=True,
        digits=dp.get_precision('Account'), default=0.00)
    icms_st_base = fields.Float(
        'Base ICMS ST', required=True,
        digits=dp.get_precision('Account'), default=0.00)
    icms_st_percent = fields.Float(
        'Percentual ICMS ST', digits=dp.get_precision('Discount'),
        default=0.00)
    icms_st_percent_reduction = fields.Float(
        u'Perc Redução de Base ICMS ST',
        digits=dp.get_precision('Discount'), default=0.00)
    icms_st_mva = fields.Float(
        'MVA Ajustado ICMS ST',
        digits=dp.get_precision('Discount'), default=0.00)
    icms_st_base_other = fields.Float(
        'Base ICMS ST Outras', required=True,
        digits=dp.get_precision('Account'), default=0.00)
    icms_cst_id = fields.Many2one(
        'account.tax.code', 'CST ICMS', domain=[('domain', '=', 'icms')])
    icms_relief_id = fields.Many2one(
        'l10n_br_account_product.icms_relief',
        string=u'Desoneração ICMS')
    issqn_manual = fields.Boolean('ISSQN Manual?', default=False)
    service_type_id = fields.Many2one(
        'l10n_br_account.service.type', u'Tipo de Serviço')
    issqn_base = fields.Float(
        'Base ISSQN', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    issqn_percent = fields.Float(
        'Perc ISSQN', required=True, digits=dp.get_precision('Discount'),
        default=0.00)
    issqn_value = fields.Float(
        'Valor ISSQN', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    issqn_suspension_process = fields.Char(u"Número do processo de suspensão")
    issqn_exigibilidade = fields.Selection(string="Exigibilidade",
                                           selection=EXIGIBILIDADE,
                                           default='1')
    ipi_manual = fields.Boolean('IPI Manual?', default=False)
    ipi_type = fields.Selection(
        [('percent', 'Percentual'), ('quantity', 'Em Valor')],
        'Tipo do IPI', required=True, default='percent')
    ipi_base = fields.Float(
        'Base IPI', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    ipi_base_other = fields.Float(
        'Base IPI Outras', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    ipi_value = fields.Float(
        'Valor IPI', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    ipi_percent = fields.Float(
        'Perc IPI', required=True, digits=dp.get_precision('Discount'),
        default=0.00)
    ipi_cst_id = fields.Many2one(
        'account.tax.code', 'CST IPI', domain=[('domain', '=', 'ipi')])
    ipi_guideline_id = fields.Many2one(
        'l10n_br_account_product.ipi_guideline',
        string=u'Enquadramento Legal IPI')
    pis_manual = fields.Boolean('PIS Manual?', default=False)
    pis_type = fields.Selection(
        [('percent', 'Percentual'), ('quantity', 'Em Valor')],
        'Tipo do PIS', required=True, default='percent')
    pis_base = fields.Float('Base PIS', required=True,
                            digits=dp.get_precision('Account'), default=0.00)
    pis_base_other = fields.Float(
        'Base PIS Outras', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    pis_value = fields.Float(
        'Valor PIS', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    pis_percent = fields.Float(
        'Perc PIS', required=True, digits=dp.get_precision('Discount'),
        default=0.00)
    pis_cst_id = fields.Many2one(
        'account.tax.code', 'CST PIS', domain=[('domain', '=', 'pis')])
    pis_st_type = fields.Selection(
        [('percent', 'Percentual'), ('quantity', 'Em Valor')],
        'Tipo do PIS ST', required=True, default='percent')
    pis_st_base = fields.Float(
        'Base PIS ST', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    pis_st_percent = fields.Float(
        'Perc PIS ST', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    pis_st_value = fields.Float(
        'Valor PIS ST', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    cofins_manual = fields.Boolean('COFINS Manual?', default=False)
    cofins_type = fields.Selection(
        [('percent', 'Percentual'), ('quantity', 'Em Valor')],
        'Tipo do COFINS', required=True, default='percent')
    cofins_base = fields.Float(
        'Base COFINS',
        required=True,
        digits=dp.get_precision('Account'),
        default=0.00)
    cofins_base_other = fields.Float(
        'Base COFINS Outras', required=True,
        digits=dp.get_precision('Account'), default=0.00)
    cofins_value = fields.Float(
        'Valor COFINS', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    cofins_percent = fields.Float(
        'Perc COFINS', required=True, digits=dp.get_precision('Discount'),
        default=0.00)
    cofins_cst_id = fields.Many2one(
        'account.tax.code', 'CST PIS', domain=[('domain', '=', 'cofins')])
    cofins_st_type = fields.Selection(
        [('percent', 'Percentual'), ('quantity', 'Em Valor')],
        'Tipo do COFINS ST', required=True, default='percent')
    cofins_st_base = fields.Float(
        'Base COFINS ST', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    cofins_st_percent = fields.Float(
        'Perc COFINS ST', required=True, digits=dp.get_precision('Discount'),
        default=0.00)
    cofins_st_value = fields.Float(
        'Valor COFINS ST', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    ii_base = fields.Float(
        'Base II', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    ii_value = fields.Float(
        'Valor II', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    ii_iof = fields.Float(
        'Valor IOF', required=True, digits=dp.get_precision('Account'),
        default=0.00)
    ii_customhouse_charges = fields.Float(
        'Despesas Aduaneiras', required=True,
        digits=dp.get_precision('Account'), default=0.00)
    insurance_value = fields.Float(
        'Valor do Seguro', digits=dp.get_precision('Account'), default=0.00)
    other_costs_value = fields.Float(
        'Outros Custos', digits=dp.get_precision('Account'), default=0.00)
    freight_value = fields.Float(
        'Frete', digits=dp.get_precision('Account'), default=0.00)
    fiscal_comment = fields.Text(u'Observação Fiscal')
    icms_dest_base = fields.Float(
        string=u'Valor da BC do ICMS na UF de destino',
        digits=dp.get_precision('Account'),
        default=0.00)
    icms_fcp_percent = fields.Float(
        string=u'% Fundo de Combate à Pobreza (FCP)',
        digits=dp.get_precision('Account'),
        default=0.00)
    icms_origin_percent = fields.Float(
        string=u'Alíquota interna da UF de destino',
        digits=dp.get_precision('Account'),
        default=0.00)
    icms_dest_percent = fields.Float(
        string=u'Alíquota interestadual das UF envolvidas',
        digits=dp.get_precision('Account'),
        default=0.00)
    icms_part_percent = fields.Float(
        string=u'Percentual provisório de partilha do ICMS Interestadual',
        digits=dp.get_precision('Account'),
        default=0.00)
    icms_fcp_value = fields.Float(
        string=(u'Valor do ICMS relativo ao Fundo de Combate à Pobreza (FCP)'
                u' da UF de destino'),
        digits=dp.get_precision('Account'),
        default=0.00)
    icms_dest_value = fields.Float(
        string=u'Valor do ICMS Interestadual para a UF de destino',
        digits=dp.get_precision('Account'),
        default=0.00)
    icms_origin_value = fields.Float(
        string=u'Valor do ICMS Interno para a UF do remetente',
        digits=dp.get_precision('Account'),
        default=0.00)
    partner_order = fields.Char(
        string=u"Código do Pedido (xPed)",
        size=15,
    )
    partner_order_line = fields.Char(
        string=u"Item do Pedido (nItemPed)",
        size=6,
    )
    csll_base = fields.Float('Base CSLL', required=True, default=0.0,
                             digits_compute=dp.get_precision('Account'))
    csll_value = fields.Float('Valor CSLL', required=True, default=0.0,
                              digits_compute=dp.get_precision('Account'))
    csll_percent = fields.Float('Perc CSLL', required=True, default=0.0,
                                digits_compute=dp.get_precision('Discount'))
    ir_base = fields.Float('Base IR', required=True, default=0.0,
                           digits_compute=dp.get_precision('Account'))
    ir_value = fields.Float('Valor IR', required=True, default=0.0,
                            digits_compute=dp.get_precision('Account'))
    ir_percent = fields.Float('Perc IR', required=True, default=0.0,
                              digits_compute=dp.get_precision('Discount'))
    inss_base = fields.Float('Base INSS', required=True, default=0.0,
                             digits_compute=dp.get_precision('Account'))
    inss_value = fields.Float('Valor INSS', required=True, default=0.0,
                              digits_compute=dp.get_precision('Account'))
    inss_percent = fields.Float('Perc. INSS', required=True, default=0.0,
                                digits_compute=dp.get_precision('Discount'))
    csll_wh_value = fields.Float('Valor CSLL retido', default=0.0,
                                 digits_compute=dp.get_precision('Discount'))
    ir_wh_value = fields.Float('Valor IRRF retido', default=0.0,
                                 digits_compute=dp.get_precision('Discount'))
    issqn_wh_value = fields.Float('Valor ISSQN retido', default=0.0,
                                 digits_compute=dp.get_precision('Discount'))
    pis_wh_value = fields.Float('Valor PIS retido', default=0.0,
                                 digits_compute=dp.get_precision('Discount'))
    cofins_wh_value = fields.Float('Valor COFINS retido', default=0.0,
                                 digits_compute=dp.get_precision('Discount'))
    inss_wh_value = fields.Float('Valor INSS retido', default=0.0,
                                 digits_compute=dp.get_precision('Discount'))
    vr_custo_comercial = fields.Float(
        string=u'Valor custo comercial',
        store=True,
        compute='_compute_price',
        digits=dp.get_precision('Account'),
        help=u'Valor dos produtos\n'
             u' + impostos pagos\n'
             u' - impostos creditados\n'
             u'Determinados durante a contabilização da compra'
    )
    vr_custo_estoque = fields.Float(
        string=u'Valor custo estoque',
        store=True,
        compute='_compute_price',
        digits=dp.get_precision('Account'),
        help=u'Custo do produto aplicado nas operações de vendas:\n'
             u' - calculado com base no metodo de formação de custo'
             u'configurado no cadastro do produto'
    )
    vr_operacao = fields.Float(
        string=u'Valor operação',
        store=True,
        compute='_compute_price',
        digits=dp.get_precision('Account'),
        help=u'Valor dos produtos\n'
             u' + frete\n'
             u' + outros custos\n'
             u' + seguro\n'
             u' - desconto'
    )
    account_move_template_id = fields.Many2one(
        comodel_name='sped.account.move.template',
        string='Modelo de partida dobrada',
        compute='_compute_move_template',
        store=True
    )

    @api.onchange("partner_order_line")
    def _check_partner_order_line(self):
        if (self.partner_order_line and
                not self.partner_order_line.isdigit()):
            raise ValidationError(
                _(u"Customer Order Line must "
                  "be a number with up to six digits")
            )

    def _amount_tax_icms(self, tax=None):
        result = {
            'icms_base': tax.get('total_base', 0.0),
            'icms_base_other': tax.get('total_base_other', 0.0),
            'icms_value': tax.get('amount', 0.0),
            'icms_percent': tax.get('percent', 0.0) * 100,
            'icms_percent_reduction': tax.get('base_reduction') * 100,
            'icms_base_type': tax.get('icms_base_type', '0'),
        }
        return result

    def _amount_tax_icmsinter(self, tax=None):
        result = {
            'icms_dest_base': tax.get('total_base', 0.0),
            'icms_dest_percent': tax.get('percent', 0.0) * 100,
            'icms_origin_percent': tax.get('icms_origin_percent', 0.0) * 100,
            'icms_part_percent': tax.get('icms_part_percent', 0.0) * 100,
            'icms_dest_value': tax.get('icms_dest_value', 0.0),
            'icms_origin_value': tax.get('icms_origin_value', 0.0),
        }
        return result

    def _amount_tax_icmsfcp(self, tax=None):
        result = {
            'icms_fcp_percent': tax.get('percent', 0.0) * 100,
            'icms_fcp_value': tax.get('amount', 0.0),
        }
        return result

    def _amount_tax_icmsst(self, tax=None):
        result = {
            'icms_st_value': tax.get('amount', 0.0),
            'icms_st_base': tax.get('total_base', 0.0),
            'icms_st_percent': tax.get('icms_st_percent', 0.0) * 100,
            'icms_st_percent_reduction': tax.get(
                'icms_st_percent_reduction',
                0.0) * 100,
            'icms_st_mva': tax.get('amount_mva', 0.0) * 100,
            'icms_st_base_other': tax.get('icms_st_base_other', 0.0),
            'icms_st_base_type': tax.get('icms_st_base_type', '4')
        }
        return result

    def _amount_tax_ipi(self, tax=None):
        result = {
            'ipi_type': tax.get('type'),
            'ipi_base': tax.get('total_base', 0.0),
            'ipi_value': tax.get('amount', 0.0),
            'ipi_percent': tax.get('percent', 0.0) * 100,
        }
        return result

    def _amount_tax_cofins(self, tax=None):
        result = {
            'cofins_base': tax.get('total_base', 0.0),
            'cofins_base_other': tax.get('total_base_other', 0.0),
            'cofins_value': tax.get('amount', 0.0),
            'cofins_percent': tax.get('percent', 0.0) * 100,
        }
        return result

    def _amount_tax_cofinsst(self, tax=None):
        result = {
            'cofins_st_type': 'percent',
            'cofins_st_base': 0.0,
            'cofins_st_percent': 0.0,
            'cofins_st_value': 0.0,
        }
        return result

    def _amount_tax_pis(self, tax=None):
        result = {
            'pis_base': tax.get('total_base', 0.0),
            'pis_base_other': tax.get('total_base_other', 0.0),
            'pis_value': tax.get('amount', 0.0),
            'pis_percent': tax.get('percent', 0.0) * 100,
        }
        return result

    def _amount_tax_pisst(self, tax=None):
        result = {
            'pis_st_type': 'percent',
            'pis_st_base': 0.0,
            'pis_st_percent': 0.0,
            'pis_st_value': 0.0,
        }
        return result

    def _amount_tax_ii(self, tax=None):
        result = {
            'ii_base': 0.0,
            'ii_value': 0.0,
        }
        return result

    def _amount_tax_ir(self, tax=None):
        result = {
            'ir_base': tax.get('total_base', 0.0),
            'ir_value': tax.get('amount', 0.0),
            'ir_percent': tax.get('percent', 0.0)*100
        }
        return result

    def _amount_tax_inss(self, tax=None):
        result = {
            'inss_base': 0.0,
            'inss_value': 0.0,
        }
        return result

    def _amount_tax_issqn(self, tax=None):
        result = {
            'issqn_base': tax.get('total_base', 0.0),
            'issqn_percent': tax.get('percent', 0.0) * 100,
            'issqn_value': tax.get('amount', 0.0),
        }
        return result

    def _amount_tax_csll(self, tax=None):
        result = {
            'csll_base': tax.get('total_base', 0.0),
            'csll_percent': tax.get('percent', 0.0) * 100,
            'csll_value': tax.get('amount', 0.0),
        }
        return result

    def _amount_tax_retcsll(self, tax=None):
        result = {
            'csll_wh_value': tax.get('amount', 0.0),
        }
        return result

    def _amount_tax_retissqn(self, tax=None):
        result = {
            'issqn_wh_value': tax.get('amount', 0.0),
        }
        return result

    def _amount_tax_retpis(self, tax=None):
        result = {
            'pis_wh_value': tax.get('amount', 0.0),
        }
        return result

    def _amount_tax_retcofins(self, tax=None):
        result = {
            'cofins_wh_value': tax.get('amount', 0.0),
        }
        return result

    def _amount_tax_retir(self, tax=None):
        result = {
            'ir_wh_value': tax.get('amount', 0.0),
        }
        return result

    def _amount_tax_retinss(self, tax=None):
        result = {
            'inss_wh_value': tax.get('amount', 0.0),
        }
        return result

    @api.multi
    def _get_tax_codes(self, product_id, fiscal_position, taxes):

        result = {}
        ctx = dict(self.env.context)
        ctx.update({'use_domain': ('use_invoice', '=', True)})
        ctx.update({'product_id': product_id})

        if fiscal_position.fiscal_category_id.journal_type in (
                'sale', 'sale_refund'):
            ctx.update({'type_tax_use': 'sale'})
        else:
            ctx.update({'type_tax_use': 'purchase'})

        product = self.env['product.product'].browse(product_id)
        ctx.update({'fiscal_type': product.fiscal_type})
        result['cfop_id'] = fiscal_position.cfop_id.id

        tax_codes = fiscal_position.with_context(
            ctx).map_tax_code(product_id, taxes)

        result['icms_cst_id'] = tax_codes.get('icms')
        result['ipi_cst_id'] = tax_codes.get('ipi')
        result['pis_cst_id'] = tax_codes.get('pis')
        result['cofins_cst_id'] = tax_codes.get('cofins')
        result['icms_relief_id'] = tax_codes.get('icms_relief')
        result['ipi_guideline_id'] = tax_codes.get('ipi_guideline')
        return result

    # TODO
    @api.multi
    def _validate_taxes(self, values):
        """Verifica se o valor dos campos dos impostos estão sincronizados
        com os impostos do Odoo"""
        context = self.env.context

        price_unit = values.get('price_unit', 0.0) or self.price_unit
        discount = values.get('discount', 0.0) or self.discount
        insurance_value = values.get(
            'insurance_value', 0.0) or self.insurance_value
        freight_value = values.get(
            'freight_value', 0.0) or self.freight_value
        other_costs_value = values.get(
            'other_costs_value', 0.0) or self.other_costs_value
        tax_ids = []
        if values.get('invoice_line_tax_id'):
            tax_ids = values.get('invoice_line_tax_id', [[6, 0, []]])[
                0][2] or self.invoice_line_tax_id.ids
        partner_id = values.get('partner_id') or self.partner_id.id
        product_id = values.get('product_id') or self.product_id.id
        quantity = values.get('quantity') or self.quantity
        fiscal_position = values.get(
            'fiscal_position') or self.fiscal_position.id

        if not product_id or not quantity or not fiscal_position:
            return {}

        result = {
            'code': None,
            'product_type': 'product',
            'service_type_id': None,
            'fiscal_classification_id': None,
            'fci': None,
        }

        if self:
            partner = self.invoice_id.partner_id
        else:
            partner = self.env['res.partner'].browse(partner_id)

        taxes = self.env['account.tax'].browse(tax_ids)
        fiscal_position = self.env['account.fiscal.position'].browse(
            fiscal_position)

        price = price_unit * (1 - discount / 100.0)

        if product_id:
            product = self.pool.get('product.product').browse(
                self._cr, self._uid, product_id, context=context)
            if product.type == 'service':
                result['product_type'] = 'service'
                result['service_type_id'] = product.service_type_id.id
            else:
                result['product_type'] = 'product'
            if product.fiscal_classification_id:
                result['fiscal_classification_id'] = \
                    product.fiscal_classification_id.id

            if product.cest_id:
                result['cest_id'] = product.cest_id.id

            if product.fci:
                result['fci'] = product.fci
                result['fiscal_comment'] = u'Res. Senado Fed. ' \
                                           u'nº13/12 FCI: ' + product.fci

            result['code'] = product.default_code
            result['icms_origin'] = product.origin

        taxes_calculed = taxes.compute_all(
            price, quantity, product=product, partner=partner,
            fiscal_position=fiscal_position,
            insurance_value=insurance_value,
            freight_value=freight_value,
            other_costs_value=other_costs_value)

        result['total_taxes'] = taxes_calculed['total_taxes']

        for tax in taxes_calculed['taxes']:
            try:
                amount_tax = getattr(
                    self, '_amount_tax_%s' % tax.get('domain', ''))
                result.update(amount_tax(tax))
            except AttributeError:
                # Caso não exista campos especificos dos impostos
                # no documento fiscal, os mesmos são calculados.
                continue

        taxes_dict = self._get_tax_codes(product_id, fiscal_position, taxes)

        for key in taxes_dict:
            result[key] = values.get(key) or taxes_dict[key]

        return result

    # TODO não foi migrado por causa do bug github.com/odoo/odoo/issues/1711
    def fields_view_get(self, cr, uid, view_id=None, view_type=False,
                        context=None, toolbar=False, submenu=False):
        result = super(AccountInvoiceLine, self).fields_view_get(
            cr, uid, view_id=view_id, view_type=view_type, context=context,
            toolbar=toolbar, submenu=submenu)
        return result

    @api.model
    def _fiscal_position_map(self, result, **kwargs):
        ctx = dict(self.env.context)
        ctx.update({'use_domain': ('use_invoice', '=', True)})
        ctx.update({'partner_id': kwargs.get('partner_id')})
        ctx.update({'product_id': kwargs.get('product_id')})
        account_obj = self.env['account.account']
        obj_fp_rule = self.env['account.fiscal.position.rule']
        partner = self.env['res.partner'].browse(kwargs.get('partner_id'))

        product_fiscal_category_id = obj_fp_rule.with_context(
            ctx).product_fiscal_category_map(
            kwargs.get('product_id'), kwargs.get('fiscal_category_id'),
            partner.state_id.id)

        if product_fiscal_category_id:
            kwargs['fiscal_category_id'] = product_fiscal_category_id

        result_rule = obj_fp_rule.with_context(ctx).apply_fiscal_mapping(
            result, **kwargs)
        result_rule['value']['fiscal_category_id'] = \
            kwargs.get('fiscal_category_id')
        if result_rule['value'].get('fiscal_position'):
            fp = self.env['account.fiscal.position'].browse(
                result_rule['value']['fiscal_position'])
            if kwargs.get('product_id'):
                product = self.env['product.product'].browse(
                    kwargs['product_id'])
                taxes = self.env['account.tax']
                ctx['fiscal_type'] = product.fiscal_type
                if ctx.get('type') in ('out_invoice', 'out_refund'):
                    ctx['type_tax_use'] = 'sale'
                    if product.taxes_id:
                        taxes |= product.taxes_id
                    elif kwargs.get('account_id'):
                        account_id = kwargs['account_id']
                        taxes |= account_obj.browse(account_id).tax_ids
                else:
                    ctx['type_tax_use'] = 'purchase'
                    if product.supplier_taxes_id:
                        taxes |= product.supplier_taxes_id
                    elif kwargs.get('account_id'):
                        account_id = kwargs['account_id']
                        taxes |= account_obj.browse(account_id).tax_ids
                tax_ids = fp.with_context(ctx).map_tax(taxes)
                result_rule['value']['invoice_line_tax_id'] = tax_ids.ids
                result['value'].update(self._get_tax_codes(
                    kwargs['product_id'], fp, tax_ids))

        return result_rule

    @api.multi
    def product_id_change(self, product, uom_id, qty=0, name='',
                          type='out_invoice', partner_id=False,
                          fposition_id=False, price_unit=False,
                          currency_id=False, company_id=None):
        ctx = dict(self.env.context)
        if type in ('out_invoice', 'out_refund'):
            ctx.update({'type_tax_use': 'sale'})
        else:
            ctx.update({'type_tax_use': 'purchase'})

        result = super(AccountInvoiceLine, self).product_id_change(
            product, uom_id, qty, name, type, partner_id,
            fposition_id, price_unit, currency_id, company_id)

        fiscal_category_id = ctx.get('parent_fiscal_category_id')

        if not fiscal_category_id or not product:
            return result
        product_obj = self.env['product.product'].browse(product)
        result['value']['name'] = product_obj.display_name
        result = self.with_context(ctx)._fiscal_position_map(
            result, partner_id=partner_id, partner_invoice_id=partner_id,
            company_id=company_id, product_id=product,
            fiscal_category_id=fiscal_category_id,
            account_id=result['value']['account_id'])
        return result

    @api.onchange('fiscal_category_id',
                  'fiscal_position',
                  'invoice_line_tax_id',
                  'quantity',
                  'price_unit',
                  'discount',
                  'insurance_value',
                  'freight_value',
                  'other_costs_value')
    def onchange_fiscal(self):
        ctx = dict(self.env.context)
        if self.invoice_id.type in ('out_invoice', 'out_refund'):
            ctx.update({'type_tax_use': 'sale'})
        else:
            ctx.update({'type_tax_use': 'purchase'})

        partner_id = self.invoice_id.partner_id.id or ctx.get('partner_id')
        company_id = self.invoice_id.company_id.id or ctx.get('company_id')
        if company_id and partner_id and self.fiscal_category_id:
            result = {'value': {}}
            kwargs = {
                'company_id': company_id,
                'partner_id': partner_id,
                'partner_invoice_id': self.invoice_id.partner_id.id,
                'product_id': self.product_id.id,
                'fiscal_category_id': self.fiscal_category_id.id,
                'context': ctx
            }
            result = self.with_context(ctx)._fiscal_position_map(
                result, **kwargs)

            kwargs.update({
                'invoice_line_tax_id': [
                    (6, 0, self.invoice_line_tax_id.ids)],
                'quantity': self.quantity,
                'price_unit': self.price_unit,
                'discount': self.discount,
                'fiscal_position': self.fiscal_position.id,
                'insurance_value': self.insurance_value,
                'freight_value': self.freight_value,
                'other_costs_value': self.other_costs_value,
            })
            result['value'].update(self._validate_taxes(kwargs))
            self.update(result['value'])

    @api.model
    def tax_exists(self, domain=None):
        result = False
        tax = self.env['account.tax'].search(domain, limit=1)
        if tax:
            result = tax
        return result

    @api.multi
    def update_invoice_line_tax_id(self, tax_id, taxes, domain):
        new_taxes = [(6, 0, [tax_id])]
        for tax in self.env['account.tax'].browse(taxes[0][2]):
            if not tax.domain == domain:
                new_taxes[0][2].append(tax.id)
        return new_taxes

    @api.multi
    def onchange_tax_icms(self, icms_base_type, icms_base, icms_base_other,
                          icms_value, icms_percent, icms_percent_reduction,
                          icms_cst_id, price_unit, discount, quantity,
                          partner_id, product_id, fiscal_position_id,
                          insurance_value, freight_value, other_costs_value,
                          invoice_line_tax_id):

        result = {'value': {}}
        # ctx = dict(self.env.context)

        # Search if exists the tax
        # domain = [('domain', '=', 'icms')]
        #
        # domain.append(('icms_base_type', '=', icms_base_type))
        #
        # percent_decimal = icms_percent / 100
        # domain.append(('amount', '=', percent_decimal))
        #
        # reduction_percent = icms_percent_reduction / 100
        # domain.append(('base_reduction', '=', reduction_percent))
        #
        # tax = self.tax_exists(domain)
        #
        # # If not exists create a new tax
        # if not tax:
        #     tax_template = self.env['account.tax'].search([
        #         ('type_tax_use', '=', DEFAULT_TAX_TYPE[ctx.get(
        #             'type_tax_use', 'out_invoice')]),
        #         ('domain', '=', 'icms'),
        #         ('amount', '=', '0.0'),
        #         ('company_id', '=', self.env.user.company_id.id),
        #     ])
        #
        #     if not tax_template:
        #         raise except_orm(_('Alerta', u'Não existe imposto\
        #                            do domínio ICMS com aliquita 0%!'))
        #
        #     tax_name = 'ICMS Interno Saída {:.2f}%'.format(icms_percent)
        #
        #     if icms_percent_reduction:
        #         tax_name = 'ICMS Interno Saída {:.2f}% Red \
        #                     {:.2f}%'.format(icms_percent,
        #                                     icms_percent_reduction)
        #
        #     tax_values = {
        #         'name': tax_name,
        #         'description': tax_name,
        #         'type_tax_use': tax_template[0].type_tax_use,
        #         'company_id': tax_template[0].company_id.id,
        #         'active': True,
        #         'type': 'percent',
        #         'amount': icms_percent / 100,
        #         'tax_discount': True,
        #         'base_reduction': icms_percent_reduction / 100,
        #         'applicable_type': 'true',
        #         'icms_base_type': icms_base_type,
        #         'domain': 'icms',
        #         'account_collected_id': (tax_template[0]
        #                                  .account_collected_id.id),
        #         'account_paid_id': tax_template[0].account_paid_id.id,
        #         'base_code_id': tax_template[0].base_code_id.id,
        #         'base_sign': 1.0,
        #         'ref_base_code_id': tax_template[0].ref_base_code_id.id,
        #         'ref_base_sign': 1.0,
        #         'tax_code_id': tax_template[0].tax_code_id.id,
        #         'tax_sign': 1.0,
        #         'ref_tax_code_id': tax_template[0].ref_tax_code_id.id,
        #         'ref_tax_sign': 1.0,
        #     }
        #     tax = self.env['account.tax'].create(tax_values)
        #
        # # Compute the tax
        # partner = self.env['res.partner'].browse(partner_id)
        # product = self.env['product.product'].browse(partner_id)
        # fiscal_position = self.env['account.fiscal.position'].browse(
        #     fiscal_position_id)
        # price = price_unit * (1 - discount / 100.0)
        # tax_compute = tax.compute_all(
        #     price, quantity, product, partner,
        #     fiscal_position=fiscal_position,
        #     insurance_value=insurance_value,
        #     freight_value=freight_value,
        #     other_costs_value=other_costs_value,
        #     base_tax=icms_base)
        #
        # # Update tax values to new values
        # result['value'].update(self._amount_tax_icms(
        # tax_compute['taxes'][0]))
        #
        # # Update invoice_line_tax_id
        # # Remove all taxes with domain ICMS
        # result['value']['invoice_line_tax_id'] = (self
        #      .update_invoice_line_tax_id(tax.id, invoice_line_tax_id,
        #                                  tax.domain))
        return result

    @api.multi
    def onchange_tax_icms_st(
            self,
            icms_st_base_type,
            icms_st_base,
            icms_st_percent,
            icms_st_percent_reduction,
            icms_st_mva,
            icms_st_base_other,
            price_unit,
            discount,
            insurance_value,
            freight_value,
            other_costs_value):
        return {'value': {}}

    @api.multi
    def onchange_tax_ipi(self, ipi_type, ipi_base, ipi_base_other,
                         ipi_value, ipi_percent, ipi_cst_id,
                         price_unit, discount, insurance_value,
                         freight_value, other_costs_value):
        return {'value': {}}

    @api.multi
    def onchange_tax_pis(self, pis_type, pis_base, pis_base_other,
                         pis_value, pis_percent, pis_cst_id,
                         price_unit, discount, insurance_value,
                         freight_value, other_costs_value):
        return {'value': {}}

    @api.multi
    def onchange_tax_pis_st(
            self,
            pis_st_type,
            pis_st_base,
            pis_st_percent,
            pis_st_value,
            price_unit,
            discount,
            insurance_value,
            freight_value,
            other_costs_value):
        return {'value': {}}

    @api.multi
    def onchange_tax_cofins(
            self,
            cofins_st_type,
            cofins_st_base,
            cofins_st_percent,
            cofins_st_value,
            price_unit,
            discount,
            insurance_value,
            freight_value,
            other_costs_value):
        return {'value': {}}

    @api.multi
    def onchange_tax_cofins_st(
            self,
            cofins_st_type,
            cofins_st_base,
            cofins_st_percent,
            cofins_st_value,
            price_unit,
            discount,
            insurance_value,
            freight_value,
            other_costs_value):
        return {'value': {}}

    @api.onchange('service_type_id')
    def onchange_service_type(self):
        exigibilidade = self.invoice_id.company_id.issqn_exigibilidade \
            or self.service_type_id.issqn_exigibilidade
        processo = self.invoice_id.company_id.issqn_suspension_process \
           or self.service_type_id.issqn_suspension_process
        self.issqn_exigibilidade = exigibilidade or '1'
        self.issqn_suspension_process = processo

    @api.model
    def create(self, vals):
        vals.update(self._validate_taxes(vals))
        return super(AccountInvoiceLine, self).create(vals)

    # TODO comentado por causa deste bug
    # https://github.com/odoo/odoo/issues/2197
    # @api.multi
    # def write(self, vals):
    #    vals.update(self._validate_taxes(vals))
    #    return super(AccountInvoiceLine, self).write(vals)

    @api.multi
    def gera_account_move_line(
            self, line_ids, template_nao_contabilizados, 
            move_template, campos_jah_contabilizados=False):
        self.ensure_one()
        
        if not campos_jah_contabilizados:
            campos_jah_contabilizados = []

        for template_item in move_template.item_ids:
            if not getattr(self, template_item.campo, False):
                template_nao_contabilizados.add(template_item)
                continue

            if template_item.campo in campos_jah_contabilizados:
                continue

            #
            # Nas notas de entrada por compra ou devolução de venda, se
            # não se vai aproveitar o crédito do imposto, ele não é
            # contabilizado à parte
            #
            if self.invoice_id.type in ('in_invoice', 'out_refund'):
                if (template_item.campo in
                        ('icms_value', 'vr_icms_sn')
                        and not self.credita_icms):
                    continue
                elif template_item.campo == 'icms_st_value' and \
                        not self.credita_icms_st:
                    continue
                elif template_item.campo == 'ipi_value' and \
                        not self.credita_ipi:
                    continue
                elif template_item.campo in ('pis_value',
                        'cofins_value') and not self.credita_pis_cofins:
                    continue

            valor = getattr(self, template_item.campo, 0)

            if not valor:
                continue

            account_debito = None
            if template_item.account_debito_id:
                account_debito = template_item.account_debito_id

            #elif template_item.campo in CAMPO_DOCUMENTO_FISCAL_ITEM:
            elif template_item.account_automatico_debito == ACCOUNT_AUTOMATICO_PRODUTO:
                product = self.product_id
                if self.invoice_id.type in ('out_invoice', 'out_refund'):
                    if product.property_account_income:
                        account_debito = product.property_account_income
                    else:
                        raise UserError(
                            u'Conta de receita não selecionada no produto.'
                        )
                elif self.invoice_id.type in ('in_invoice', 'in_refund'):
                    if product.property_account_expense:
                        account_debito = product.property_account_expense
                    else:
                        raise UserError(
                            u'Conta de Despesas não selecionada no produto.'
                        )
            elif template_item.account_automatico_debito == ACCOUNT_AUTOMATICO_PARTICIPANTE:
                partner = self.invoice_id.partner_id
                if self.invoice_id.type in ('out_invoice', 'out_refund'):
                    account_debito = \
                        partner.property_account_receivable
                elif self.invoice_id.type in ('in_invoice', 'in_refund'):
                    account_debito = partner.property_account_payable

            if account_debito is not None:
                dados = {
                    'account_id': account_debito.id,
                    # 'move_id': account_move.id,
                    # 'sped_documento_item_id': self.id,
                    'name': self.product_id.name,
                    'narration': template_item.campo,
                    'debit': valor,
                    # 'currency_id': self.invoice_id.currency_id.id,
                }
                line_ids.append((0, 0, dados))

            account_credito = None
            if template_item.account_credito_id:
                account_credito = template_item.account_credito_id

            #elif template_item.campo in CAMPO_DOCUMENTO_FISCAL_ITEM:
            elif template_item.account_automatico_credito == ACCOUNT_AUTOMATICO_PRODUTO:
                product = self.product_id
                if self.invoice_id.type in ('out_invoice', 'out_refund'):
                    if product.property_account_income:
                        account_credito = product.property_account_income
                    else:
                        raise UserError(
                            u'Conta de Recebimento não selecionada no produto.'
                        )
                elif self.invoice_id.type in ('in_invoice', 'in_refund'):
                    if product.property_account_expense:
                        account_credito = product.property_account_expense
                    else:
                        raise UserError(
                            u'Conta de Despesas não selecionada no produto.'
                        )

            elif template_item.account_automatico_credito == ACCOUNT_AUTOMATICO_PARTICIPANTE:
                partner = self.invoice_id.partner_id
                if self.invoice_id.type in ('out_invoice', 'out_refund'):
                    if partner.property_account_receivable:
                        account_credito = \
                            partner.property_account_receivable
                    else:
                        raise UserError(
                            u'Conta de Recebimento'
                            u' não selecionada no parceiro.'
                        )
                elif self.invoice_id.type in ('in_invoice', 'in_refund'):
                    if partner.property_account_payable:
                        account_credito = partner.property_account_payable
                    else:
                        raise UserError(
                            u'Conta de Pagamento não selecionada no parceiro.'
                        )

            if account_credito is not None:
                dados = {
                    'account_id': account_credito.id,
                    # 'move_id': account_move.id,
                    # 'sped_documento_item_id': self.id,
                    'name': self.product_id.name,
                    'narration': template_item.campo,
                    'credit': valor,
                    # 'currency_id': self.invoice_id.currency_id.id,
                }
                line_ids.append((0, 0, dados))

            campos_jah_contabilizados.append(template_item.campo)

        if move_template.parent_id:
            self.gera_account_move_line(
                line_ids=line_ids,
                template_nao_contabilizados=template_nao_contabilizados,
                move_template=move_template.parent_id,
                campos_jah_contabilizados=campos_jah_contabilizados,
            )


class AccountInvoiceTax(models.Model):
    _inherit = 'account.invoice.tax'

    @api.v8
    def compute(self, invoice):
        tax_grouped = {}
        currency = invoice.currency_id.with_context(
            date=invoice.date_invoice or fields.Date.context_today(invoice))
        company_currency = invoice.company_id.currency_id
        for line in invoice.invoice_line:
            taxes = line.invoice_line_tax_id.compute_all(
                (line.price_unit * (1 - (line.discount or 0.0) / 100.0)),
                line.quantity, product=line.product_id,
                partner=invoice.partner_id,
                fiscal_position=line.fiscal_position,
                insurance_value=line.insurance_value,
                freight_value=line.freight_value,
                other_costs_value=line.other_costs_value)['taxes']
            for tax in taxes:
                val = {
                    'invoice_id': invoice.id,
                    'name': tax['name'],
                    'amount': tax['amount'],
                    'manual': False,
                    'sequence': tax['sequence'],
                    'base': currency.round(
                        tax.get('total_base',
                                tax.get('price_unit', 0.00) *
                                line['quantity'])),
                }
                if invoice.type in ('out_invoice', 'in_invoice'):
                    val['base_code_id'] = tax['base_code_id']
                    val['tax_code_id'] = tax['tax_code_id']
                    val['base_amount'] = currency.compute(
                        val['base'] * tax['base_sign'],
                        company_currency, round=False)
                    val['tax_amount'] = currency.compute(
                        val['amount'] * tax['tax_sign'],
                        company_currency, round=False)
                    val['account_id'] = tax[
                        'account_collected_id'] or line.account_id.id
                    val['account_analytic_id'] = tax[
                        'account_analytic_collected_id']
                else:
                    val['base_code_id'] = tax['ref_base_code_id']
                    val['tax_code_id'] = tax['ref_tax_code_id']
                    val['base_amount'] = currency.compute(
                        val['base'] * tax['ref_base_sign'],
                        company_currency, round=False)
                    val['tax_amount'] = currency.compute(
                        val['amount'] * tax['ref_tax_sign'],
                        company_currency, round=False)
                    val['account_id'] = tax[
                        'account_paid_id'] or line.account_id.id
                    val['account_analytic_id'] = tax[
                        'account_analytic_paid_id']

                # If the taxes generate moves on the same financial account
                # as the invoice line and no default analytic account is
                # defined at the tax level, propagate the analytic account
                # from the invoice line to the tax line. This is necessary
                # in situations were (part of) the taxes cannot be reclaimed,
                # to ensure the tax move is allocated to the proper analytic
                # account.
                if not val.get('account_analytic_id') and\
                        line.account_analytic_id and\
                        val['account_id'] == line.account_id.id:
                    val['account_analytic_id'] = line.account_analytic_id.id

                key = (val['tax_code_id'], val[
                       'base_code_id'], val['account_id'])
                if key not in tax_grouped:
                    tax_grouped[key] = val
                else:
                    tax_grouped[key]['base'] += val['base']
                    tax_grouped[key]['amount'] += val['amount']
                    tax_grouped[key]['base_amount'] += val['base_amount']
                    tax_grouped[key]['tax_amount'] += val['tax_amount']

        for t in tax_grouped.values():
            t['base'] = currency.round(t['base'])
            t['amount'] = currency.round(t['amount'])
            t['base_amount'] = currency.round(t['base_amount'])
            t['tax_amount'] = currency.round(t['tax_amount'])

        return tax_grouped
