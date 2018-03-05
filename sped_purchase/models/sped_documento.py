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

    recebido = fields.Boolean(
        string='Produtos recebidos?',
        compute='_compute_recebido',
        default=False,
    )

    @api.multi
    def receber_produtos(self):
        self.ensure_one()
        pickings = self.purchase_order_ids.mapped('picking_ids').filtered(
            lambda pick: pick.state not in ['cancel', 'done']
        )
        return {
            'name': _("Receber Produtos"),
            'view_mode': 'tree,form',
            'view_type': 'form',
            'res_model': 'stock.picking',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'domain': [('id', 'in', pickings.ids)]
        }

    @api.multi
    def _compute_recebido(self):
        for documento in self:
            documento.recebido = all(
                pick.state in ['cancel', 'done'] for pick in
                self.purchase_order_ids.mapped('picking_ids')
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

    @api.onchange('purchase_order_ids')
    def purchase_order_change(self):
        self.ensure_one()
        if len(self.mapped('purchase_order_ids')) > 1:
            return {}
        elif not self.purchase_order_ids:
            res = {'value': {'item_ids': [(1, item.id, {
                'purchase_ids': [(6, 0, [])],
                'purchase_line_ids': [(6, 0, [])]
            }) for item in self.mapped('item_ids')]}}
            return res
        for item in self.mapped('item_ids'):
            item.purchase_ids = self.purchase_order_ids.ids
        self.item_ids.find_lines()

    def _criar_picking_entrada(self):
        if not self.purchase_order_ids:
            super(SpedDocumento, self)._criar_picking_entrada()

