# -*- coding: utf-8 -*-
#
#  Copyright 2017 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
#

from odoo import api, fields, models, _


class SpedDocumento(models.Model):
    _inherit = 'sped.documento'

    purchase_order_ids = fields.Many2many(
        comodel_name='purchase.order',
        string='Adicionar Pedido de Compra',
        relation='purchase_order_sped_documento_rel',
        copy=False,
    )

    def _preparar_sped_documento_item(self, item):
        dados = {
            'documento_id': self.id,
            'produto_id': item.produto_id.id,
            'quantidade': item.quantidade - item.qty_invoiced,
            'vr_unitario': item.vr_unitario,
            'vr_frete': item.vr_frete,
            'vr_seguro': item.vr_seguro,
            'vr_desconto': item.vr_desconto,
            'vr_outras': item.vr_outras,
        }
        return dados

    @api.onchange('purchase_order_ids')
    def _onchange_atualiza_po_itens(self):
        """
        Atualiza o campo purchase_ids dos itens do pedido de compra
        de acordo com o campo purchase_order_ids do pedido de compra
        """
        for record in self:
            if not record.purchase_order_ids or len(
                    record.purchase_order_ids) > 1:
                return {}

            dados = {
                'purchase_ids': [(6, False, record.purchase_order_ids[0].ids)]
            }

            for item in record.item_ids:
                item.write(dados)

    # # Carregar linhas da Purchase Order
    # @api.onchange('purchase_order_ids')
    # def purchase_order_change(self):
    #     if not self.purchase_order_ids:
    #         return {}
    #     elif len(self.purchase_order_ids) == 1:
    #         dados = {
    #             'empresa_id': self.purchase_order_ids.empresa_id.id,
    #             'operacao_id': self.purchase_order_ids.operacao_id.id,
    #             'modelo': self.purchase_order_ids.operacao_id.modelo,
    #             'emissao': self.purchase_order_ids.operacao_id.emissao,
    #             'participante_id': self.purchase_order_ids.participante_id.id,
    #             'condicao_pagamento_id': self.purchase_order_ids.condicao_pagamento_id.id if \
    #                 self.purchase_order_ids.condicao_pagamento_id else False,
    #             'transportadora_id': self.purchase_order_ids.transportadora_id.id if \
    #                 self.purchase_order_ids.transportadora_id else False,
    #             'modalidade_frete': self.purchase_order_ids.modalidade_frete,
    #         }
    #         dados.update(self.purchase_order_ids.prepara_dados_documento())
    #         self.update(dados)
    #         self.update(self._onchange_empresa_id()['value'])
    #         self.update(self._onchange_operacao_id()['value'])
    #
    #         if self.purchase_order_ids.presenca_comprador:
    #             self.presenca_comprador = self.purchase_order_ids.presenca_comprador
    #
    #         self.update(self._onchange_serie()['value'])
    #         self.update(self._onchange_participante_id()['value'])
    #
    #     for pedido in self.mapped('purchase_order_ids'):
    #         for item in pedido.order_line - \
    #                 self.item_ids.mapped('purchase_line_ids'):
    #             dados = self._preparar_sped_documento_item(item)
    #             contexto = {
    #                 'forca_vr_unitario': dados['vr_unitario']
    #             }
    #             documento_item = self.item_ids.mesclar_linhas(
    #                 dados, item, contexto
    #             )
    #             if documento_item:
    #                 self.item_ids += documento_item
    #                 self.item_ids[-1].update(
    #                     item.prepara_dados_documento_item()
    #                 )
    #     return {}

    # @api.onchange('purchase_order_ids')
    # def purchase_order_change(self):
    #     self.ensure_one()
    #     if not self.purchase_order_ids or len(self .mapped('purchase_order_ids')) > 1:
    #         return {}
    #     for item in self.mapped('item_ids'):
    #         item.write({'purchase_ids': [(6, False, self.purchase_order_ids.ids)]})

    # @api.onchange('participante_id', 'item_ids.purchase_ids', 'item_ids.purchase_line_ids', 'empresa_id')
    # def _onchange_allowed_purchase_ids(self):
    #     result = {}
    #
    #     # A PO can be selected only if at least one PO line is not already in the invoice
    #     purchase_line_ids = self.item_ids.mapped('purchase_line_ids')
    #     purchase_ids = self.item_ids.mapped('purchase_ids').filtered(lambda r: r.order_line <= purchase_line_ids)
    #
    #     result['domain'] = {'purchase_order_ids': [
    #         ('invoice_status', '=', 'to invoice'),
    #         ('id', 'not in', purchase_ids.ids),
    #     ]}
    #
    #     if self.participante_id:
    #         result['domain']['purchase_order_ids'].append(
    #             ('participante_id', '=', self.participante_id.id)
    #         )
    #
    #     if self.empresa_id:
    #         result['domain']['purchase_order_ids'].append(
    #             ('empresa_id', '=', self.empresa_id.id)
    #         )
    #
    #     return result

    def _criar_picking_entrada(self):
        if not self.purchase_order_ids:
            super(SpedDocumento, self)._criar_picking_entrada()

    def executa_depois_create(self):
        for documento in self:
            for item in documento.item_ids:
                item.calcula_impostos()

    @api.model
    def create(self, vals):
        documentos = super(SpedDocumento, self).create(vals)
        documentos.executa_depois_create()
        return documentos

    @api.multi
    def write(self, vals):
        res = super(SpedDocumento, self).write()
        self.executa_depois_create()
        return res
