# -*- coding: utf-8 -*-
#
# Copyright 2018 KMEE INFORMATICA LTDA
#   Luis Felipe Mileo <mileo@kmee.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from __future__ import division, print_function, unicode_literals

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError
from odoo.addons.l10n_br_base.constante_tributaria import (
    SITUACAO_NFE_AUTORIZADA,
    SITUACAO_NFE_EM_DIGITACAO
)


class SpedDocumentoItemDevolucao(models.TransientModel):
    _name = b"sped.documento.item.devolucao"
    _rec_name = 'product_id'

    product_id = fields.Many2one(
        comodel_name='sped.produto',
        string="Produto",
        required=True
    )
    quantity = fields.Float(
        string='Quantidade',
        digits=dp.get_precision('Product Unit of Measure'),
        required=True
    )
    wizard_id = fields.Many2one(
        'sped.documento.devolucao',
        string="Wizard"
    )
    item_id = fields.Many2one('sped.documento.item', "Item")


class SpedDocumentoDevolucao(models.TransientModel):
    _name = b'sped.documento.devolucao'
    _description = 'Devolucao de documento fiscal'

    operacao_devolucao_id = fields.Many2one(
        comodel_name='sped.operacao',
        string='Operação de Devolução',
        required=True,
    )

    devolucao_item_ids = fields.One2many(
        comodel_name='sped.documento.item.devolucao',
        inverse_name='wizard_id',
        string='Itens'
    )

    @api.model
    def default_get(self, fields):
        if len(self.env.context.get('active_ids', list())) > 1:
            raise UserError("Você só pode fazer uma devolução por vez!")
        res = super(SpedDocumentoDevolucao, self).default_get(fields)

        devolucao_itens = []
        documento = self.env['sped.documento'].browse(
            self.env.context.get('active_id')
        )
        if documento:
            if documento.situacao_nfe != SITUACAO_NFE_AUTORIZADA:
                raise UserError(_("Você só pode devolver notas autorizadas"))
            if documento.operacao_id.operacao_devolucao_id:
                res.update({
                    'operacao_devolucao_id':
                        documento.operacao_id.operacao_devolucao_id.id,
                })

            for item in documento.item_ids:
                devolucao_itens.append((0, 0, {
                    'product_id': item.produto_id.id,
                    'quantity': item.quantidade,
                    'item_id': item.id
                }))

            if not devolucao_itens:
                raise UserError(_("Você não pode devolver nenhum dos itens!"))

            if 'devolucao_item_ids' in fields:
                res.update({'devolucao_item_ids': devolucao_itens})
        return res

    @api.multi
    def _criar_devolucao(self):
        documento = self.env['sped.documento'].browse(
            self.env.context['active_id']
        )

        return_itens = self.devolucao_item_ids.mapped('item_id')
        unreturn_itens = self.env['sped.documento.item']
        # for item in return_itens:
        # TODO: Verificar quais itens já foram retornados

        operacao = self.operacao_devolucao_id

        novo_sped_documento_id = documento.copy({
            'operacao_id': operacao.id,
            'modelo': operacao.modelo,
            'emissao': operacao.emissao,
            'finalidade_nfe': operacao.finalidade_nfe,
            'entrada_saida': operacao.entrada_saida,
            'situacao_nfe': SITUACAO_NFE_EM_DIGITACAO,
            # 'origin': documento.name,
            'item_ids': [],  # Não copiamos os itens, fazemos isso depois
        })

        referencia_ids = documento._prepare_subsequente_referenciado()
        novo_sped_documento_id._referencia_documento(referencia_ids)

        returned_lines = 0
        for return_line in self.devolucao_item_ids:
            if not return_line.item_id:
                raise UserError(
                    _("""Se você criou uma linha de devolução manualmente, \n
                      por favor delete ela para prosseguir"""))
            new_qty = return_line.quantity
            if new_qty:

                returned_lines += 1
                return_line.item_id.copy({
                    'documento_id': novo_sped_documento_id.id,
                    'quantidade': new_qty,
                    # 'origin_returned_move_id': return_line.move_id.id,
                })

        novo_sped_documento_id.gera_documento()

        if not returned_lines:
            raise UserError(
                _("Please specify at least one non-zero quantity."))

        # novo_sped_documento_id = novo_sped_documento_id.gera_documento()
        return novo_sped_documento_id

    @api.multi
    def criar_devolucao(self):
        for wizard in self:
            novo_sped_documento_id = wizard._criar_devolucao()
            return novo_sped_documento_id.action_view_documento()

