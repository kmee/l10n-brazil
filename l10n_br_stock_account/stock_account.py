# -*- coding: utf-8 -*-
# Copyright (C) 2014  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import models, fields, api


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    def _default_fiscal_category(self):
        company = self.env['res.company'].browse(self.env.user.company_id.id)
        return company.stock_fiscal_category_id

    fiscal_category_id = fields.Many2one(
        'l10n_br_account.fiscal.category', 'Categoria Fiscal',
        readonly=True, domain="[('state', '=', 'approved')]",
        states={'draft': [('readonly', False)]},
        default=_default_fiscal_category)
    fiscal_position_id = fields.Many2one(
        'account.fiscal.position', u'Posição Fiscal',
        domain="[('fiscal_category_id','=',fiscal_category_id)]",
        readonly=True, states={'draft': [('readonly', False)]})

    def _fiscal_position_map(self, **kwargs):
        ctx = dict(self.env.context)
        if ctx.get('fiscal_category_id'):
            kwargs['fiscal_category_id'] = ctx.get('fiscal_category_id')
        ctx.update({'use_domain': ('use_picking', '=', True)})
        return self.env['account.fiscal.position.rule'].with_context(
            ctx).apply_fiscal_mapping(**kwargs)

    @api.multi
    def onchange_fiscal_category_id(self, fiscal_category_id, partner_id,
                                    company_id):

        result = {'value': {'fiscal_position': None}}

        if not partner_id or not company_id or not fiscal_category_id:
            return result

        # TODO waiting migration super method to new api
        partner_invoice_id = self.pool.get('res.partner').address_get(
            self._cr, self._uid, [partner_id], ['invoice'])['invoice']
        partner_shipping_id = self.pool.get('res.partner').address_get(
            self._cr, self._uid, [partner_id], ['delivery'])['delivery']

        kwargs = {
            'partner_id': partner_id,
            'partner_invoice_id': partner_invoice_id,
            'partner_shipping_id': partner_shipping_id,
            'company_id': company_id,
            'context': dict(self.env.context),
            'fiscal_category_id': fiscal_category_id,
        }
        return self._fiscal_position_map(result, **kwargs)

    def onchange_company_id(self, partner_id, company_id):

        result = {'value': {'fiscal_position': False}}

        if not partner_id or not company_id:
            return result

        # TODO waiting migration super method to new api
        partner_invoice_id = self.pool.get('res.partner').address_get(
            self._cr, self._uid, [partner_id], ['invoice'])['invoice']
        partner_shipping_id = self.pool.get('res.partner').address_get(
            self._cr, self._uid, [partner_id], ['delivery'])['delivery']

        kwargs = {
            'partner_id': partner_id,
            'partner_invoice_id': partner_invoice_id,
            'partner_shipping_id': partner_shipping_id,
            'company_id': company_id,
            'context': self.env.context,
        }
        return self._fiscal_position_map(result, **kwargs)

    @api.model
    def _create_invoice_from_picking(self, picking, vals):
        result = {}

        comment = ''
        if picking.fiscal_position.inv_copy_note:
            comment += picking.fiscal_position.note or ''
        if picking.sale_id and picking.sale_id.copy_note:
            comment += picking.sale_id.note or ''
        if picking.note:
            comment += ' - ' + picking.note

        result['partner_shipping_id'] = picking.partner_id.id

        result['comment'] = comment
        result['fiscal_category_id'] = picking.fiscal_category_id.id
        result['fiscal_position'] = picking.fiscal_position.id

        if picking.fiscal_category_id.journal_type in ('sale_refund',
                                                       'purchase_refund'):
            result['nfe_purpose'] = '4'

        vals.update(result)
        return super(StockPicking, self)._create_invoice_from_picking(picking,
                                                                      vals)


class StockMove(models.Model):
    _inherit = "stock.move"

    fiscal_category_id = fields.Many2one(
        'l10n_br_account.fiscal.category', 'Categoria Fiscal', readonly=True,
        domain="[('type', '=', 'output'), ('journal_type', '=', 'sale')]",
        states={'draft': [('readonly', False)],
                'sent': [('readonly', False)]})
    fiscal_position_id = fields.Many2one(
        'account.fiscal.position', 'Fiscal Position', readonly=True,
        domain="[('fiscal_category_id','=',fiscal_category_id)]",
        states={'draft': [('readonly', False)],
                'sent': [('readonly', False)]})

    def _fiscal_position_map(self, result, **kwargs):
        ctx = dict(self.env.context)
        kwargs['context'].update({'use_domain': ('use_picking', '=', True)})
        ctx.update({'use_domain': ('use_picking', '=', True)})

    @api.multi
    def onchange_product_id(self, product_id, location_id,
                            location_dest_id, partner_id):
        context = dict(self.env.context)
        parent_fiscal_category_id = context.get('parent_fiscal_category_id')
        if context.get('company_id'):
            company_id = context['company_id']
        else:
            company_id = self.env.user.company_id.id

        result = {'value': {}}
        result['value']['invoice_state'] = context.get('parent_invoice_state')

        if parent_fiscal_category_id and self.product_id and self.partner_id:

            partner = self.env['res.partner'].browse(partner_id)
            obj_fp_rule = self.env['account.fiscal.position.rule']
            product_fc_id = obj_fp_rule.product_fiscal_category_map(
                product_id, parent_fiscal_category_id, partner.state_id.id)

            if product_fc_id:
                parent_fiscal_category_id = product_fc_id

            result['value']['fiscal_category_id'] = parent_fiscal_category_id

            kwargs = {
                'partner_id': partner_id,
                'partner_invoice_id': partner_id,
                'partner_shipping_id': partner_id,
                'fiscal_category_id': parent_fiscal_category_id,
                'company_id': company_id,
                'context': context
            }

            result.update(self._fiscal_position_map(**kwargs))

        result_super = super(StockMove, self).onchange_product_id()
        if result_super.get('value'):
            result_super.get('value').update(result['value'])
        else:
            result_super.update(result)
        return result_super

    @api.multi
    def onchange_fiscal_category_id(self, fiscal_category_id, partner_id,
                                    company_id):

    def _get_new_picking_values(self):
        """ Prepares a new picking for this move as it could not be assigned to
        another picking. This method is designed to be inherited. """
        result = super(StockMove, self)._get_new_picking_values()
        result.update({
            'fiscal_category_id': self.fiscal_category_id.id,
            'fiscal_position_id': self.fiscal_position_id.id,
        })
        return result
