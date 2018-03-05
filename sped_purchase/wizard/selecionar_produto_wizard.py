# -*- coding: utf-8 -*-
# Copyright (C) 2017 Gabriel Cardoso de Faria - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
from odoo import models, fields, api, _


class SelecionarProduto(models.TransientModel):
    _name = b'sped.documento.item.selecionar.produto'

    documento_item_id = fields.Many2one(
        comodel_name='sped.documento.item',
        string='Item',
    )

    produto_id = fields.Many2one(
        comodel_name='sped.produto',
        related='documento_item_id.produto_id',
    )

    @api.onchange('documento_item_id')
    def _onchange_documento_item_id(self):
        if not self.documento_item_id:
            return {}
        item = self.documento_item_id
        documento = item.documento_id
        partner = documento.participante_id.partner_id
        currency = partner.property_purchase_currency_id or \
                   self.env.user.company_id.currency_id
        dados = {
            'nome': item.produto_nome,
            'codigo': item.produto_codigo,
            'codigo_barras': item.produto_codigo_barras,
            'codigo_barras_tributacao':
                item.produto_codigo_barras_tributacao,
            'unidade_id': item.unidade_id.id,
            'unidade_tributacao_id':
                item.unidade_tributacao_id.id,
            'ncm_id': item._busca_ncm(item.produto_ncm,
                                      item.produto_ncm_ex),
            'preco_custo': item.vr_unitario,
        }
        dados_produto = {}
        for key in dados.keys():
            dados_produto['default_' + key] = dados[key]
        return {'context': {'produto_id': dados_produto}}
