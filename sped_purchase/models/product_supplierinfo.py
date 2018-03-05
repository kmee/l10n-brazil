# -*- coding: utf-8 -*-
#
# Copyright 2017 Kmee Informática -
#   Gabriel Cardoso de Faria <gabriel.cardoso@kmee.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#
from odoo import fields, models, api


class ProductSuppliferInfo(models.Model):
    _inherit = 'product.supplierinfo'

    produto_id = fields.Many2one(
        comodel_name='sped.produto',
        string='Produto no estoque',
        compute='_compute_produto_id',
        inverse='_inverse_produto_id',
    )

    participante_id = fields.Many2one(
        comodel_name='sped.participante',
        string='Parceiro',
        readonly=True,
    )
    cest_id = fields.Many2one(
        comodel_name='sped.cest',
        string='CEST'
    )
    codigo_barras = fields.Char(
        string='Código de barras',
        size=14,
        index=True,
    )
    codigo_barras_tributacao = fields.Char(
        string='Código de barras para tributação comercial',
        size=14,
        index=True,
    )
    unidade_id = fields.Many2one(
        comodel_name='sped.unidade',
        string='Unidade',
    )
    unidade_tributacao_id = fields.Many2one(
        comodel_name='sped.unidade',
        string='Unidade para tributação comercial',
    )
    ncm_id = fields.Many2one(
        comodel_name='sped.ncm',
        string='NCM'
    )
    cfop_id = fields.Many2one(
        comodel_name='sped.cfop',
        string='CFOP',
        ondelete='restrict',
        index=True,
    )

    documento_item_ids = fields.One2many(
        comodel_name='sped.documento.item',
        inverse_name='seller_id'
    )

    @api.depends('product_tmpl_id', 'product_id')
    def _compute_produto_id(self):
        product_obj = self.env['product.product']
        produto_obj = self.env['sped.produto']
        for sup_info in self:
            if sup_info.product_id:
                product_tmpl_id = sup_info.product_id.product_tmpl_id
                product_id = sup_info.product_id
            elif sup_info.product_tmpl_id:
                product_tmpl_id = sup_info.product_tmpl_id
                product_id = product_obj.search([
                    ('product_tmpl_id', '=', sup_info.product_tmpl_id.id)
                ], limit=1)
            else:
                continue
            produto_id = produto_obj.search([
                ('product_id', '!=', False),
                ('product_id', '=', product_id and product_id.id)
            ])
            sup_info.product_tmpl_id = product_tmpl_id and product_tmpl_id.id
            sup_info.product_id = product_id and product_id.id
            sup_info.produto_id = produto_id and produto_id.id

    @api.depends('produto_id')
    def _inverse_produto_id(self):
        for sup_info in self:
            if sup_info.produto_id and not sup_info.product_id:
                product_id = sup_info.produto_id.product_id
                product_tmpl_id = product_id.product_tmpl_id
                sup_info.product_tmpl_id = product_tmpl_id.id
                sup_info.product_id = product_id.id
