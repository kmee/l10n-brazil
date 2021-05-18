# Copyright 2020 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from lxml import etree

from erpbrasil.base import misc

from odoo import api, fields, models
from odoo.tools.float_utils import float_round as round


class DocumentLine(models.Model):
    _inherit = 'l10n_br_fiscal.document.line'

    fiscal_deductions_value = fields.Monetary(
        string='Fiscal Deductions',
        default=0.00,
    )
    other_retentions_value = fields.Monetary(
        string='Other Retentions',
        default=0.00,
    )

    cnae_main_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.cnae",
        related='company_id.cnae_main_id',
        string="Main CNAE")

    cnae_secondary_ids = fields.Many2many(
        comodel_name="l10n_br_fiscal.cnae",
        related='company_id.cnae_secondary_ids',
        string="Secondary CNAE")

    cnae_id = fields.Many2one(
        comodel_name='l10n_br_fiscal.cnae',
        string='CNAE Code',
        domain="['|', "
               "('id', 'in', cnae_secondary_ids), "
               "('id', '=', cnae_main_id)]",
    )

    @api.onchange("product_id")
    def _onchange_product_id_fiscal(self):
        super(DocumentLine, self)._onchange_product_id_fiscal()
        if self.product_id and self.product_id.fiscal_deductions_value:
            self.fiscal_deductions_value = \
                self.product_id.fiscal_deductions_value

    def _compute_taxes(self, taxes, cst=None):
        discount_value = self.discount_value
        self.discount_value += self.fiscal_deductions_value
        res = super(DocumentLine, self)._compute_taxes(taxes, cst)
        self.discount_value = discount_value
        return res

    @api.model
    def fields_view_get(self, view_id=None, view_type="form",
                        toolbar=False, submenu=False):
        model_view = super(DocumentLine, self).fields_view_get(
            view_id, view_type, toolbar, submenu)

        if view_type == 'form':
            try:
                doc = etree.fromstring(model_view.get('arch'))
                field = doc.xpath("//field[@name='issqn_wh_value']")[0]
                parent = field.getparent()
                parent.insert(parent.index(field)+1, etree.XML(
                    '<field name="other_retentions_value"/>'
                ))

                model_view["arch"] = etree.tostring(doc, encoding='unicode')
            except Exception:
                return model_view
        return model_view

    def prepare_line_servico(self):
        return {
            'valor_servicos': round(self.amount_fiscal_operation or 0.0, 2),
            'valor_deducoes': round(self.fiscal_deductions_value or 0.0, 2),
            'valor_pis': round(self.pis_value or 0.0, 2),
            'valor_pis_retido': round(self.pis_wh_value or 0.0, 2),
            'valor_cofins': '%.2f' % self.cofins_value,
            'valor_cofins_retido': round(self.cofins_wh_value or 0.0, 2),
            'valor_inss': round(self.inss_value or 0.0, 2),
            'valor_inss_retido': round(self.inss_wh_value or 0.0, 2),
            'valor_ir': round(self.irpj_value or 0.0, 2),
            'valor_ir_retido': round(self.irpj_wh_value or 0.0, 2),
            'valor_csll': round(self.csll_value or 0.0, 2),
            'valor_csll_retido': round(self.csll_wh_value or 0.0, 2),
            'iss_retido': '1' if self.issqn_wh_value else '2',
            'valor_iss': round(self.issqn_value or 0.0, 2),
            'valor_iss_retido': round(self.issqn_wh_value or 0.0, 2),
            'outras_retencoes': round(self.other_retentions_value or 0.0, 2),
            'base_calculo': round(self.issqn_base or 0.0, 2),
            'aliquota': float(self.issqn_percent / 100),
            'valor_liquido_nfse': round(self.amount_financial or 0.0, 2),
            'item_lista_servico':
                self.service_type_id.code and
                self.service_type_id.code.replace('.', ''),
            'codigo_tributacao_municipio':
                self.city_taxation_code_id.code or '',
            'discriminacao': str(self.name[:120] or ''),
            'codigo_cnae': misc.punctuation_rm(self.cnae_id.code) or None,
        }
