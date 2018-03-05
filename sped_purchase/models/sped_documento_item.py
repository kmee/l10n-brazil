# -*- coding: utf-8 -*-
#
#  Copyright 2017 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
#

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class SpedDocumentoItem(models.Model):
    _inherit = 'sped.documento.item'

    purchase_line_ids = fields.Many2many(
        string='Linha do pedido',
        comodel_name='purchase.order.line',
        copy=False,
    )

    purchase_ids = fields.Many2many(
        string='Pedido de compra',
        comodel_name='purchase.order',
        copy=False,
    )

    pode_alterar_quantidade = fields.Boolean(
        string='Pode alterar a quantidade?',
        compute='_compute_quantidade_alteravel',
        default=True,
    )

    seller_id = fields.Many2one(
        string='Dados do fornecedor',
        comodel_name='product.supplierinfo',
        compute='_compute_set_seller_id'
    )

    @api.multi
    def find_lines(self):
        for item in self:
            data = {
                'produto_id': item.produto_id,
                'quantidade': item.quantidade,
                'vr_unitario': item.vr_unitario,
                'vr_frete': item.vr_frete,
                'vr_seguro': item.vr_seguro,
                'vr_desconto': item.vr_desconto,
                'vr_outras': item.vr_outras,
            }
            for linha in item.purchase_ids.mapped('order_line') - \
                    item.mapped('purchase_line_ids'):
                if all(linha[field] == data[field] for field in data.keys()):
                    item.purchase_line_ids += linha

    @api.onchange('purchase_ids', 'purchase_line_ids')
    def _onchange_purchase_line_ids(self):

        for purchase in self.mapped('purchase_ids'):
            if purchase not in self.documento_id.mapped('purchase_order_ids'):
                self.documento_id.purchase_order_ids += purchase

        result = {'domain': {
            'purchase_line_ids': [],
            'purchase_ids': [('invoice_status', '=', 'to invoice')]}}

        if self.purchase_ids:
            result['domain']['purchase_line_ids'].append(
                ('order_id', 'in', self.purchase_ids.ids)
            )

        if self.partner_id:
            result['domain']['purchase_line_ids'].append(
                ('partner_id', '=', self.partner_id.id)
            )
            result['domain']['purchase_ids'].append(
                ('partner_id', '=', self.partner_id.id)
            )

        if self.empresa_id:
            result['domain']['purchase_line_ids'].append(
                ('empresa_id', '=', self.empresa_id.id)
            )
            result['domain']['purchase_ids'].append(
                ('empresa_id', '=', self.empresa_id.id)
            )

        if self.produto_id:
            result['domain']['purchase_line_ids'].append(
                ('produto_id', '=', self.produto_id.id)
            )

        if self.vr_unitario:
            result['domain']['purchase_line_ids'].append(
                ('vr_unitario', '=', self.vr_unitario)
            )

        return result

    @api.constrains('purchase_line_ids', 'quantidade')
    def _check_m2m_quantity(self):
        for item in self:
            if len(item.purchase_line_ids) > 1:
                for linha in item.mapped('purchase_line_ids'):
                    if len(linha.documento_item_ids) > 1:
                        raise ValidationError(_(
                            'Impossível relacionar item de documento com '
                            'linhas de pedido de compras que não tenham '
                            'relação única com esse item.'
                        ))
            elif item.purchase_line_ids:
                total = 0.0
                for doc_item in item.purchase_line_ids.mapped(
                        'documento_item_ids'):
                    total += doc_item.quantidade
                if total > item.purchase_line_ids.quantidade:
                    raise ValidationError(_(
                        'Quantidade do produto ' + item.produto_id.nome +
                        'ultrapassa o disponível na linha do pedido de compra.'
                    ))

    @api.depends('purchase_line_ids')
    def _compute_quantidade_alteravel(self):
        for item in self:
            if len(item.purchase_line_ids) > 1:
                item.pode_alterar_quantidade = False
                quantidade = 0.0
                for linha in item.mapped('purchase_line_ids'):
                    quantidade += linha.quantidade
                item.quantidade = quantidade
            else:
                item.pode_alterar_quantidade = True

    @api.multi
    def selecionar_produto(self):
        return {
            'name': _("Selecionar Produto"),
            'view_mode': 'form',
            'view_type': 'form',
            'view_id': self.env.ref(
                'sped_purchase.selecionar_produto_wizard').id,
            'res_model': 'sped.documento.item.selecionar.produto',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': {'default_documento_item_id': self.id},
        }

    @api.depends('produto_id')
    def _compute_set_seller_id(self):
        for item in self:
            if not item.produto_id:
                continue
            documento = item.documento_id
            partner = documento.participante_id.partner_id
            currency = partner.property_purchase_currency_id or \
                       self.env.user.company_id.currency_id
            item.calcula_impostos()
            item.seller_id = item.produto_id.product_id._select_seller(
                partner_id=partner, quantity=item.quantidade,
                uom_id=item.unidade_id.uom_id
            )
            dados = {
                'produto_id': item.produto_id.id,
                'name': partner.id,
                'product_uom': item.unidade_id.uom_id.id,
                'min_qty': 0.0,
                'price': documento.currency_id.compute(
                    item.vr_unitario, currency),
                'currency_id': currency.id,
                'delay': 0,
                'participante_id': documento.participante_id.id,
                'cest_id': item._busca_cest(item.produto_cest),
                'product_name': item.produto_nome,
                'product_code': item.produto_codigo,
                'codigo_barras': item.produto_codigo_barras,
                'codigo_barras_tributacao':
                    item.produto_codigo_barras_tributacao,
                'unidade_id': item._busca_unidade(
                    item.produto_unidade, False),
                'unidade_tributacao_id': item._busca_unidade(
                    item.produto_unidade_tributacao, False),
                'ncm_id': item._busca_ncm(item.produto_ncm,
                                          item.produto_ncm_ex),
                'cfop_id': item.cfop_original_id.id
                if documento.emissao == '1' else item.cfop_id.id,
            }
            if not item.seller_id:
                item.seller_id = \
                    self.env['product.supplierinfo'].search([
                        ('product_name', '=', dados['product_name']),
                        ('codigo_barras', '=', dados['codigo_barras']),
                        ('product_code', '=', dados['product_code']),
                    ]) or self.env['product.supplierinfo'].create(dados)
            item.seller_id.write(dados)
