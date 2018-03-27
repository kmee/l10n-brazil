# -*- coding: utf-8 -*-
#
#  Copyright 2017 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
#

from odoo import api, fields, models, _


class SpedDocumento(models.Model):
    _inherit = 'sped.documento'

    purchase_id = fields.Many2one(
        comodel_name='purchase.order',
        string='Adicionar Pedido de Compra',
        copy=False,
    )

    def _preparar_sped_documento_item(self, item):
        quantidade = 0.0
        if self.stock_picking_id:
            quantidades = self.stock_picking_id.mapped('move_lines').filtered(
                lambda move: move.purchase_line_id.id == item.id).mapped(
                'product_qty')
            for qty in quantidades:
                quantidade += qty
        dados = {
            'product_id': item.product_id.id,
            'documento_id': self.id,
            'quantidade': quantidade or (item.quantidade - item.qty_invoiced),
            'vr_unitario': item.vr_unitario,
            'vr_frete': item.vr_frete,
            'vr_seguro': item.vr_seguro,
            'vr_desconto': item.vr_desconto,
            'vr_outras': item.vr_outras,
        }
        return dados

    # Carregar linhas da Purchase Order
    @api.onchange('purchase_id')
    def purchase_order_change(self):
        if not self.purchase_id:
            return {}
        pick = self.purchase_id.picking_ids.filtered(
            lambda pick: pick.state != 'cancel'
        ) - self.purchase_id.invoice_ids.mapped('stock_picking_id')
        pick = pick.filtered(lambda pick: pick.state == 'done') or pick
        dados = {
            'empresa_id': self.purchase_id.empresa_id.id,
            'operacao_id': self.purchase_id.operacao_id.id,
            'modelo': self.purchase_id.operacao_id.modelo,
            'emissao': self.purchase_id.operacao_id.emissao,
            'partner_id': self.purchase_id.partner_id.id,
            'condicao_pagamento_id':
                self.purchase_id.condicao_pagamento_id.id or False,
            'natureza_operacao_id':
                self.purchase_id.operacao_id.natureza_operacao_id.id or False,
            'serie': self.purchase_id.operacao_id.serie or False,
            'presenca_comprador':
                self.purchase_id.presenca_comprador or False,
            'stock_picking_id': pick and pick[0].id or False,
        }
        dados.update(self._onchange_empresa_id()['value'])
        dados.update(self._onchange_operacao_id()['value'])
        dados.update(self._onchange_serie()['value'])
        self.update(dados)

        novos_itens = self.env['sped.documento.item']
        for item in self.purchase_id.order_line - \
                self.item_ids.mapped('purchase_line_id'):
            dados = self._preparar_sped_documento_item(item)
            dados.update(
                item.prepara_dados_documento_item()
            )
            documento_item = novos_itens.new(dados)
            documento_item.calcula_impostos()
            novos_itens += documento_item

        self.item_ids |= novos_itens
        self.purchase_id = False
        self.importado_xml = True
        return {}

    @api.onchange('sped_stock_id')
    def stock_picking_change(self):
        if not self.stock_picking_id:
            return {}
        dados = {
            'transportadora_id':
                self.stock_picking_id.transportadora_id.id or False,
            'modalidade_frete':
                self.stock_picking_id.modalidade_frete or False,
        }
