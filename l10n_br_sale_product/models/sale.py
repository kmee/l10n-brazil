# -*- coding: utf-8 -*-
# Copyright (C) 2014  Renato Lima - Akretion                                  #
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

from odoo.addons import decimal_precision as dp
from odoo.addons.l10n_br_base.tools.misc import calc_price_ratio


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.multi
    @api.depends('order_line.price_unit', 'order_line.tax_id',
                 'order_line.discount', 'order_line.product_uom_qty',
                 'order_line.freight_value', 'order_line.insurance_value',
                 'order_line.other_costs_value')
    def _amount_all_wrapper(self):
        """
        Wrapper because of direct method passing as parameter
        for function fields
        """
        return self._amount_all()

    @api.multi
    def _amount_all(self):
        for order in self:
            order.amount_untaxed = 0.0
            order.amount_tax = 0.0
            order.amount_total = 0.0
            order.amount_extra = 0.0
            order.amount_discount = 0.0
            order.amount_gross = 0.0

            amount_tax = amount_untaxed = \
                amount_discount = amount_gross = \
                amount_extra = 0.0
            for line in order.order_line:
                amount_tax += self._amount_line_tax(line)
                amount_extra += (line.insurance_value +
                                 line.freight_value +
                                 line.other_costs_value)
                amount_untaxed += line.price_subtotal
                amount_discount += line.discount_value
                amount_gross += line.price_gross

            order.amount_tax = order.pricelist_id.currency_id.round(
                amount_tax)
            order.amount_untaxed = order.pricelist_id.currency_id.round(
                amount_untaxed)
            order.amount_extra = order.pricelist_id.currency_id.round(
                amount_extra)
            order.amount_total = (order.amount_untaxed +
                                  order.amount_tax +
                                  order.amount_extra)
            order.amount_discount = order.pricelist_id.currency_id.round(
                amount_discount)
            order.amount_gross = order.pricelist_id.currency_id.round(
                amount_gross)

    @api.model
    def _amount_line_tax(self, line):
        value = 0.0
        price = line._calc_line_base_price()
        qty = line._calc_line_quantity()

        for computed in line.tax_id.compute_all(
                price_unit=price,
                quantity=qty,
                partner=line.order_id.partner_invoice_id,
                product=line.product_id,
                # line.order_id.partner_id,
                fiscal_position=line.fiscal_position_id,
                insurance_value=line.insurance_value,
                freight_value=line.freight_value,
                other_costs_value=line.other_costs_value)['taxes']:
            tax = self.env['account.tax'].browse(computed['id'])
            if not tax.tax_group_id.tax_discount:
                value += computed.get('amount', 0.0)
        return value

    @api.model
    def _default_ind_pres(self):
        company = self.env['res.company'].browse(self.env.user.company_id.id)
        return company.default_ind_pres

    @api.one
    def _get_costs_value(self):
        """ Read the l10n_br specific functional fields. """
        freight = costs = insurance = 0.0
        for line in self.order_line:
            freight += line.freight_value
            insurance += line.insurance_value
            costs += line.other_costs_value
        self.amount_freight = freight
        self.amount_costs = costs
        self.amount_insurance = insurance

    @api.one
    def _set_amount_freight(self):
        for line in self.order_line:
            if not self.amount_gross:
                break
            line.write({
                'freight_value': calc_price_ratio(
                    line.price_gross,
                    self.amount_freight,
                    line.order_id.amount_gross),
            })
        return True

    @api.one
    def _set_amount_insurance(self):
        for line in self.order_line:
            if not self.amount_gross:
                break
            line.write({
                'insurance_value': calc_price_ratio(
                    line.price_gross,
                    self.amount_insurance,
                    line.order_id.amount_gross),
            })
        return True

    @api.one
    def _set_amount_costs(self):
        for line in self.order_line:
            if not self.amount_gross:
                break
            line.write({
                'other_costs_value': calc_price_ratio(
                    line.price_gross,
                    self.amount_costs,
                    line.order_id.amount_gross),
            })
        return True

    ind_pres = fields.Selection(selection=[
        ('0', u'Não se aplica (por exemplo,'
              u' Nota Fiscal complementar ou de ajuste)'),
        ('1', u'Operação presencial'),
        ('2', u'Operação não presencial, pela Internet'),
        ('3', u'Operação não presencial, Teleatendimento'),
        ('4', u'NFC-e em operação com entrega em domicílio'),
        ('5', u'Operação presencial, fora do estabelecimento'),
        ('9', u'Operação não presencial, outros')], string=u'Tipo de operação',
        readonly=True, states={'draft': [('readonly', False)]}, required=False,
        help=u'Indicador de presença do comprador no estabelecimento \
             comercial no momento da operação.',
        default=_default_ind_pres)
    amount_untaxed = fields.Float(
        compute='_amount_all_wrapper', string='Untaxed Amount',
        digits=dp.get_precision('Account'), store=True,
        help="The amount without tax.", track_visibility='always')
    amount_tax = fields.Float(
        compute='_amount_all_wrapper', string='Taxes', store=True,
        digits=dp.get_precision('Account'), help="The tax amount.")
    amount_total = fields.Float(
        compute='_amount_all_wrapper', string='Total', store=True,
        digits=dp.get_precision('Account'), help="The total amount.")
    amount_extra = fields.Float(
        compute='_amount_all_wrapper', string='Extra',
        digits=dp.get_precision('Account'), store=True,
        help="The total amount.")
    amount_discount = fields.Float(
        compute='_amount_all_wrapper', string='Desconto (-)',
        digits=dp.get_precision('Account'), store=True,
        help="The discount amount.")
    amount_gross = fields.Float(
        compute='_amount_all_wrapper', string='Vlr. Bruto',
        digits=dp.get_precision('Account'),
        store=True, help="The discount amount.")
    amount_freight = fields.Float(
        compute=_get_costs_value, inverse=_set_amount_freight,
        string='Frete', default=0.00, digits=dp.get_precision('Account'),
        readonly=True, states={'draft': [('readonly', False)]})
    amount_costs = fields.Float(
        compute=_get_costs_value, inverse=_set_amount_costs,
        string='Outros Custos', default=0.00,
        digits=dp.get_precision('Account'),
        readonly=True, states={'draft': [('readonly', False)]})
    amount_insurance = fields.Float(
        compute=_get_costs_value, inverse=_set_amount_insurance,
        string='Seguro', default=0.00, digits=dp.get_precision('Account'),
        readonly=True, states={'draft': [('readonly', False)]})

    @api.model
    def _fiscal_comment(self, order):
        fc_comment = []
        fc_ids = []

        fp_comment = super(SaleOrder, self)._fiscal_comment(order)

        for line in order.order_line:
            if line.product_id.fiscal_classification_id:
                fc = line.product_id.fiscal_classification_id
                if fc.inv_copy_note and fc.note:
                    if fc.id not in fc_ids:
                        fc_comment.append(fc.note)
                        fc_ids.append(fc.id)

        return fp_comment + fc_comment

    @api.model
    def _make_invoice(self, order, lines):
        context = dict(self.env.context)
        company = self.env['res.company'].browse(
            self.env.user.company_id.id)
        context.update(
            {'fiscal_document_code': company.product_invoice_id.code})
        return super(
            SaleOrder, self.with_context(context))._make_invoice(
            order, lines)


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    @api.depends('price_unit', 'tax_id', 'discount', 'product_uom_qty')
    def _amount_line(self):
        for record in self:
            price = record._calc_line_base_price()
            qty = record._calc_line_quantity()
            taxes = record.tax_id.compute_all(
                price_unit=price,
                quantity=qty,
                product=record.product_id,
                partner=record.order_id.partner_invoice_id,
                fiscal_position=record.fiscal_position_id,
                insurance_value=record.insurance_value,
                freight_value=record.freight_value,
                other_costs_value=record.other_costs_value)

            record.price_subtotal = \
                record.order_id.pricelist_id.currency_id.round(
                    taxes['total_excluded'])
            record.price_gross = record._calc_price_gross(qty)
            record.discount_value = \
                record.order_id.pricelist_id.currency_id.round(
                    record.price_gross - (price * qty))

    insurance_value = fields.Float('Insurance',
                                   default=0.0,
                                   digits=dp.get_precision('Account'))
    other_costs_value = fields.Float('Other costs',
                                     default=0.0,
                                     digits=dp.get_precision('Account'))
    freight_value = fields.Float('Freight',
                                 default=0.0,
                                 digits=dp.get_precision('Account'))
    discount_value = fields.Float(compute='_amount_line',
                                  string='Vlr. Desc. (-)',
                                  digits=dp.get_precision('Sale Price'))
    price_gross = fields.Float(compute='_amount_line',
                               string='Vlr. Bruto',
                               digits=dp.get_precision('Sale Price'))
    price_subtotal = fields.Float(compute='_amount_line',
                                  string='Subtotal',
                                  digits=dp.get_precision('Sale Price'))
    customer_order = fields.Char(
        string=u"Pedido do Cliente",
        size=15,
    )
    customer_order_line = fields.Char(
        string=u"Item do Pedido do Cliente",
        size=6,
    )

    @api.onchange("customer_order_line")
    def _check_customer_order_line(self):
        if (self.customer_order_line and
                not self.customer_order_line.isdigit()):
            raise ValidationError(
                _(u"Customer order line must be "
                  "a number with up to six digits")
            )

    @api.multi
    def _prepare_invoice_line(self, qty):
        self.ensure_one()
        result = super(SaleOrderLine, self)._prepare_invoice_line(
            qty)

        result['insurance_value'] = self.insurance_value
        result['other_costs_value'] = self.other_costs_value
        result['freight_value'] = self.freight_value
        result['partner_order'] = self.customer_order
        result['partner_order_line'] = self.customer_order_line

        # FIXME
        # Necessário informar estes campos pois são related do
        # objeto account.invoice e quando o método create do
        # account.invoice.line é invocado os valores são None
        result['company_id'] = self.order_id.company_id.id
        result['partner_id'] = self.order_id.partner_id.id

        if self.product_id.fiscal_type == 'product':
            if self.fiscal_position_id:
                cfop = self.fiscal_position_id.cfop_id
                if cfop:
                    result['cfop_id'] = cfop.id
        return result
