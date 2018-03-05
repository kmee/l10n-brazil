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

    documento_item_ids = fields.Many2many(
        comodel_name='sped.documento.item',
        inverse_name='purchase_line_ids',
    )

    def prepara_dados_documento_item(self):
        self.ensure_one()

        return {
            'purchase_line_ids': [(4, self.id)],
            'purchase_ids': [(4, self.order_id.id)],
        }

    @api.onchange('produto_id')
    def onchange_product_id_date(self):
        if not self.order_id:
            return

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
        if self.produto_id:
            self.name = self.produto_id.nome

    @api.depends('modelo', 'emissao')
    def _compute_permite_alteracao(self):
        for item in self:
            item.permite_alteracao = True

    @api.depends('documento_item_ids.quantidade',
                 'documento_item_ids.seller_id',
                 'documento_item_ids.documento_id.recebido')
    def _compute_qty_invoiced(self):
        for linha in self:
            itens = linha.documento_item_ids.filtered(
                lambda item: item.documento_id.recebido)
            if len(itens) > 1:
                total = 0.0
                for item in itens:
                    total += \
                        item.seller_id.unidade_id.uom_id._compute_quantity(
                            item.quantidade, item.unidade_id.uom_id
                        )
                linha.qty_invoiced = total
            elif itens:
                if len(itens.purchase_line_ids) > 1:
                    for linha_item in itens.mapped('purchase_line_ids'):
                        linha_item.qty_invoiced = linha_item.quantidade
                elif itens.purchase_line_ids:
                    linha.qty_invoiced = \
                        itens.seller_id.unidade_id.uom_id._compute_quantity(
                            itens.quantidade, itens.unidade_id.uom_id
                        )
