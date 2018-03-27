# -*- coding: utf-8 -*-
# Copyright 2017 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from odoo import api, fields, models, _
import odoo.addons.decimal_precision as dp
from odoo.addons.sped_imposto.models.sped_calculo_imposto_item import (
    SpedCalculoImpostoItem
)


class PurchaseOrderLine(SpedCalculoImpostoItem, models.Model):
    _inherit = b'purchase.order.line'

    @api.depends('invoice_lines.documento_id.situacao_nfe')
    def _compute_qty_invoiced(self):
        for line in self:
            qty = 0.0
            for inv_line in line.invoice_lines:
                if inv_line.documento_id.situacao_nfe not in ['cancelada']:
                    qty += inv_line.unidade_id.uom_id._compute_quantity(
                        inv_line.quantidade, line.product_uom)
            line.qty_invoiced = qty

    is_brazilian = fields.Boolean(
        string=u'Is a Brazilian Invoice?',
        related='order_id.is_brazilian',
    )
    empresa_id = fields.Many2one(
        related='order_id.empresa_id',
        readonly=True,
    )
    operacao_id = fields.Many2one(
        related='order_id.operacao_produto_id',
        readonly=True,
    )
    data_emissao = fields.Datetime(
        related='order_id.date_order',
        readonly=True,
    )

    #
    # Campos readonly
    #
    unidade_readonly_id = fields.Many2one(
        comodel_name='sped.unidade',
        string='Unidade',
        ondelete='restrict',
        compute='_compute_readonly',
    )
    unidade_tributacao_readonly_id = fields.Many2one(
        comodel_name='sped.unidade',
        string='Unidade para tributação',
        ondelete='restrict',
        compute='_compute_readonly',
    )
    vr_produtos_readonly = fields.Monetary(
        string='Valor do produto/serviço',
        compute='_compute_readonly',
    )
    vr_produtos_tributacao_readonly = fields.Monetary(
        string='Valor do produto/serviço para tributação',
        compute='_compute_readonly',
    )
    vr_operacao_readonly = fields.Monetary(
        string='Valor da operação',
        compute='_compute_readonly',
    )
    vr_operacao_tributacao_readonly = fields.Monetary(
        string='Valor da operação para tributação',
        compute='_compute_readonly',
    )
    vr_nf_readonly = fields.Monetary(
        string='Valor da NF',
        compute='_compute_readonly',
    )
    vr_fatura_readonly = fields.Monetary(
        string='Valor da fatura',
        compute='_compute_readonly',
    )
    vr_unitario_custo_comercial_readonly = fields.Float(
        string='Custo unitário comercial',
        compute='_compute_readonly',
        digits=dp.get_precision('SPED - Valor Unitário'),
    )
    vr_custo_comercial_readonly = fields.Monetary(
        string='Custo comercial',
        compute='_compute_readonly',
    )
    peso_bruto_readonly = fields.Monetary(
        string='Peso bruto',
        currency_field='currency_peso_id',
        compute='_compute_readonly',
    )
    peso_liquido_readonly = fields.Monetary(
        string='Peso líquido',
        currency_field='currency_peso_id',
        compute='_compute_readonly',
    )
    quantidade_especie_readonly = fields.Float(
        string='Quantidade por espécie/embalagem',
        digits=dp.get_precision('SPED - Quantidade'),
        compute='_compute_readonly',
    )
    permite_alteracao = fields.Boolean(
        string='Permite alteração?',
        compute='_compute_permite_alteracao',
    )

    documento_id = fields.Many2one(
        comodel_name='purchase.order',
        related='order_id',
        readonly=True,
    )

    invoice_lines = fields.One2many(
        comodel_name='sped.documento.item',
        inverse_name='purchase_line_id',
        string="Bill Lines",
        readonly=True,
        copy=False
    )

    qty_invoiced = fields.Float(
        compute=_compute_qty_invoiced,
        digits=dp.get_precision('Product Unit of Measure'),
        store=True)

    def prepara_dados_documento_item(self):
        self.ensure_one()

        return {
            'purchase_line_id': self.id,
            'purchase_id': self.order_id.id,
        }

    @api.onchange('product_id')
    def onchange_product_id_date(self):
        if not self.order_id:
            return {}

        if not self.data_emissao:
            warning = {
                'title': _('Warning!'),
                'message': _(
                    'Por favor defina a data da fatura, \n'
                    'para permtir o cálculo correto dos impostos'),
            }
            return {'warning': warning}
        if not (self.order_id.operacao_produto_id):
            warning = {
                'title': _('Warning!'),
                'message': _(
                    'Por favor defina a operação'),
            }
            return {'warning': warning}
        if self.product_id:
            self.name = self.product_id.display_name
        return {}

    @api.depends('modelo', 'emissao')
    def _compute_permite_alteracao(self):
        for item in self:
            item.permite_alteracao = True
