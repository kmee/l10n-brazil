# -*- coding: utf-8 -*-
###############################################################################
#
# Copyright (C) 2013  Renato Lima - Akretion
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################

from openerp import models, api


class AccountFiscalPosition(models.Model):
    """Override class to implement custom mapping tax methods to
    defini brazilian taxes using new fields"""
    _inherit = 'account.fiscal.position'

    @api.v7
    def map_tax(self, cr, uid, fposition_id, taxes, context=None):
        """Custom method called in old api"""
        result = []
        if not context:
            context = {}
        if fposition_id and fposition_id.company_id and \
                context.get('type_tax_use') in ('sale', 'all'):
            if context.get('fiscal_type', 'product') == 'product':
                company_tax_ids = self.pool.get('res.company').read(
                    cr, uid, fposition_id.company_id.id, ['product_tax_ids'],
                    context=context)['product_tax_ids']
            else:
                company_tax_ids = self.pool.get('res.company').read(
                    cr, uid, fposition_id.company_id.id, ['service_tax_ids'],
                    context=context)['service_tax_ids']

            company_taxes = self.pool.get('account.tax').browse(
                cr, uid, company_tax_ids, context=context)
            if taxes:
                all_taxes = taxes + company_taxes
            else:
                all_taxes = company_taxes
            taxes = all_taxes

        if not taxes:
            return []
        if not fposition_id:
            return map(lambda x: x.id, taxes)
        for t in taxes:
            ok = False
            tax_src = False
            for tax in fposition_id.tax_ids:
                tax_src = tax.tax_src_id and tax.tax_src_id.id == t.id
                tax_code_src = tax.tax_code_src_id and \
                    tax.tax_code_src_id.id == t.tax_code_id.id

                if tax_src or tax_code_src:
                    if tax.tax_dest_id:
                        result.append(tax.tax_dest_id.id)
                    ok = True
            if not ok:
                result.append(t.id)

        return list(set(result))

    @api.multi
    def _map_tax(self, product_id, taxes):
        result = {}
        if not product_id:
            return result
        product = self.env['product.product'].browse(product_id)

        product_fc = product.fiscal_classification_id
        if self.company_id and \
                self.env.context.get('type_tax_use') in ('sale', 'all'):
            if self.env.context.get('fiscal_type', 'product') == 'product':
                company_taxes = self.company_id.product_tax_definition_line
                for tax_def in company_taxes:
                    if tax_def.tax_id:
                        taxes |= tax_def.tax_id
                        result[tax_def.tax_id.domain] = {
                            'tax': tax_def.tax_id,
                            'tax_code': tax_def.tax_code_id,
                            'icms_relief': tax_def.tax_icms_relief_id,
                            'ipi_guideline':  tax_def.tax_ipi_guideline_id,
                        }
            else:
                company_taxes = self.company_id.service_tax_definition_line
                for tax_def in company_taxes:
                    if tax_def.tax_id:
                        taxes |= tax_def.tax_id
                        result[tax_def.tax_id.domain] = {
                            'tax': tax_def.tax_id,
                            'tax_code': tax_def.tax_code_id,
                        }
            product_ncm_tax_def = product_fc.sale_tax_definition_line


        else:
            product_ncm_tax_def = product_fc.purchase_tax_definition_line

        for ncm_tax_def in product_ncm_tax_def:
            if ncm_tax_def.tax_id:
                result[ncm_tax_def.tax_id.domain] = {
                    'tax': ncm_tax_def.tax_id,
                    'tax_code': ncm_tax_def.tax_code_id,
                    'icms_relief': ncm_tax_def.tax_icms_relief_id,
                    'ipi_guideline':  ncm_tax_def.tax_ipi_guideline_id,
                }
        result = self._map_analysis(result, product, taxes)
        return result

    @api.v8
    def map_tax(self, taxes):
        """Custom method called in new api"""
        result = self.env['account.tax'].browse()
        taxes_codes = self._map_tax(self.env.context.get('product_id'), taxes)
        for tax in taxes_codes:
            if taxes_codes[tax].get('tax'):
                result |= taxes_codes[tax].get('tax')
        return result
