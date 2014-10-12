# -*- encoding: utf-8 -*-
# #############################################################################
#
#    Copyright (C) 2014 KMEE (http://www.kmee.com.br)
#    @author Luis Felipe Mileo <mileo@kmee.com.br>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import time

from openerp.osv import orm, fields
from openerp.addons import decimal_precision as dp


class AccountInvoice(orm.Model):
    _inherit = 'account.invoice'

    _columns = {
        'issqn_wh': fields.boolean(u'Retém ISSQN'),
        'issqn_value_wh': fields.float('Valor da retenção do PIS',
                                       digits_compute=dp.get_precision('Account')),
        'pis_wh': fields.boolean(u'Retém PIS'),
        'pis_value_wh': fields.float('Valor da retenção do PIS',
                                     digits_compute=dp.get_precision('Account')),
        'cofins_wh': fields.boolean(u'Retém COFINS'),
        'cofins_value_wh': fields.float('Valor da retenção do Cofins',
                                        digits_compute=dp.get_precision('Account')),
        'csll_wh': fields.boolean(u'Retém CSLL'),
        'csll_value_wh': fields.float('Valor da retenção de CSLL',
                                      digits_compute=dp.get_precision('Account')),
        'irrf_wh': fields.boolean(u'Retém IRRF'),
        'irrf_base': fields.float('Base de calculo retenção do IRRF',
                                  digits_compute=dp.get_precision('Account')),
        'irrf_value_wh': fields.float('Valor da retenção de IRRF',
                                      digits_compute=dp.get_precision('Account')),
        'inss_wh': fields.boolean(u'Retém INSS'),
        'inss_base': fields.float('Base de Cálculo da Retenção da Previdência Social',
                                  digits_compute=dp.get_precision('Account')),
        'inss_value_wh': fields.float('Valor da Retenção da Previdência Social ',
                                      digits_compute=dp.get_precision('Account')),
        # 'icms_st_value_wh': fields.float('Valor ICMS ST', required=True,
        #    digits_compute=dp.get_precision('Account')),
    }

    def _whitholding_map(self, cr, uid, result, context=None, **kwargs):
        #TODO: Implementar o mapeamento cliente x empresa.

        if not context:
            context = {}

        obj_partner = self.pool.get('res.partner').browse(
            cr, uid, kwargs.get('partner_id', False))
        obj_company = self.pool.get('res.company').browse(
            cr, uid, kwargs.get('company_id', False))

        result['value']['issqn_wh'] = obj_company.issqn_wh and  obj_partner.partner_fiscal_type_id.issqn_wh
        result['value']['inss_wh'] = obj_company.inss_wh and  obj_partner.partner_fiscal_type_id.inss_wh
        result['value']['pis_wh'] = obj_company.pis_wh and  obj_partner.partner_fiscal_type_id.pis_wh
        result['value']['cofins_wh'] = obj_company.cofins_wh and  obj_partner.partner_fiscal_type_id.cofins_wh
        result['value']['csll_wh'] = obj_company.csll_wh and  obj_partner.partner_fiscal_type_id.csll_wh
        result['value']['irrf_wh'] =  obj_company.irrf_wh and  obj_partner.partner_fiscal_type_id.irrf_wh

        return result


    def onchange_partner_id(self, cr, uid, ids, type, partner_id,
                            date_invoice=False, payment_term=False,
                            partner_bank_id=False, company_id=False,
                            fiscal_category_id=False):

        result = super(AccountInvoice, self).onchange_partner_id(
            cr, uid, ids, type, partner_id, date_invoice, payment_term,
            partner_bank_id, company_id, fiscal_category_id)

        return self._whitholding_map(
            cr, uid, result, False, partner_id=partner_id,
            partner_invoice_id=partner_id, company_id=company_id,
            fiscal_category_id=fiscal_category_id)

    def finalize_invoice_move_lines(self, cr, uid, invoice_browse, move_lines):
        move_lines = super(AccountInvoice, self).finalize_invoice_move_lines(cr, uid, invoice_browse, move_lines)
        #TODO: Verificar os totais dos impostos e implementar as retenções.

        return move_lines

    def compute_invoice_totals(self, cr, uid, inv, company_currency, ref, invoice_move_lines, context=None):
        total, total_currency, invoice_move_lines = super(AccountInvoice, self).compute_invoice_totals(cr, uid, inv,
                                                                                                       company_currency,
                                                                                                       ref,
                                                                                                       invoice_move_lines,
                                                                                                       context=None)
        return total, total_currency, invoice_move_lines


class AccountInvoiceLine(orm.Model):
    _inherit = 'account.invoice.line'

    # _columns = {
    # TODO: Implmentar o calculo de retenção de ISS que varia por item.
    # }

    def fields_view_get(self, cr, uid, view_id=None, view_type=False,
                        context=None, toolbar=False, submenu=False):
        result = super(AccountInvoiceLine, self).fields_view_get(
            cr, uid, view_id=view_id, view_type=view_type, context=context,
            toolbar=toolbar, submenu=submenu)

        return result

    def product_id_change(self, cr, uid, ids, product, uom, qty=0, name='',
                          type='out_invoice', partner_id=False,
                          fposition_id=False, price_unit=False,
                          currency_id=False, context=None, company_id=False,
                          parent_fiscal_category_id=False,
                          parent_fposition_id=False):

        result = super(AccountInvoiceLine, self).product_id_change(
            cr, uid, ids, product, uom, qty, name, type, partner_id,
            fposition_id, price_unit, currency_id, context, company_id,
            parent_fiscal_category_id, parent_fposition_id)

        return result


class AccountInvoiceTax(orm.Model):
    _inherit = 'account.invoice.tax'

    def move_line_get(self, cr, uid, invoice_id):
        res = super(AccountInvoiceTax, self).move_line_get(cr, uid, invoice_id)

        return res


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: