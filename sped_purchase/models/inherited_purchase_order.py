# -*- coding: utf-8 -*-
# Copyright 2017 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.addons.sped_imposto.models.sped_calculo_imposto import (
    SpedCalculoImposto
)
from odoo.addons.sped_imposto.models.sped_calculo_imposto_produto_servico \
    import SpedCalculoImpostoProdutoServico
from odoo.addons.l10n_br_base.constante_tributaria \
    import SITUACAO_FISCAL_SPED_CONSIDERA_ATIVO


class PurchaseOrder(SpedCalculoImpostoProdutoServico, models.Model):
    _inherit = 'purchase.order'

    @api.depends('order_line.invoice_lines.documento_id.situacao_nfe')
    def _compute_invoice(self):
        for order in self:
            invoices = self.env['sped.documento']
            for line in order.order_line:
                invoices |= line.invoice_lines.mapped('documento_id')
            order.invoice_ids = invoices
            order.invoice_count = len(invoices)

    invoice_ids = fields.Many2many(
        'sped.documento',
        compute=_compute_invoice,
        string='Bills',
        copy=False
    )
    invoice_count = fields.Integer(
        compute=_compute_invoice,
        string='# of Bills',
        copy=False,
        default=0
    )

    item_ids = fields.One2many(
        comodel_name='purchase.order.line',
        inverse_name='order_id',
        related='order_line',
    )

    operacao_id = fields.Many2one(
        comodel_name='sped.operacao',
        related='operacao_produto_id',
    )

    operacao_produto_id = fields.Many2one(
        comodel_name='sped.operacao'
    )

    operacao_servico_id = fields.Many2one(
        comodel_name='sped.operacao'
    )

    order_line_count = fields.Integer(
        compute='_compute_order_line_count'
    )

    @api.depends('order_line')
    def _compute_order_line_count(self):
        for pedido in self:
            pedido.order_line_count = len(pedido.order_line)

    @api.model
    def _prepare_picking(self):
        res = super(PurchaseOrder, self)._prepare_picking()
        res['operacao_id'] = self.operacao_produto_id.id
        return res

    def _get_date(self):
        """
        Return the document date
        Used in _amount_all_wrapper
        """
        return self.date_order

    @api.one
    @api.depends(
        'order_line.price_total',
        #
        # Campos Brasileiros
        #
        'order_line.vr_nf',
        'order_line.vr_fatura',
    )
    def _amount_all(self):
        if not self.is_brazilian:
            return super(PurchaseOrder, self)._amount_all()
        dados = {
            'amount_untaxed': self.vr_operacao,
            'amount_tax': self.vr_nf - self.vr_operacao,
            'amount_total': self.vr_fatura,
        }
        self.update(dados)

    @api.multi
    def action_view_invoice(self):
        action = self.env.ref('sped.sped_documento_recebimento_nfe_acao')
        result = action.read()[0]

        # override the context to get rid of the default filtering
        result['context'] = {
            'default_emissao': '1',
            'default_entrada_saida': '0',
            'default_modelo': '55',
            'manual': True,
            'default_purchase_id': self.id,
        }
        result['domain'] = \
            "[('id', 'in', " + str(self.invoice_ids.ids) + ")]"
        if self.invoice_count == 1:
            res = self.env.ref(
                'sped_purchase.sped_documento_recebimento_nfe_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = self.invoice_ids.id
        return result

    @api.multi
    def button_invoiced(self):
        self.ensure_one()
        return {
            'name': 'Importar NF-e',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'sped_purchase.consulta_status_documento',
            'view_id': self.env.ref('sped_purchase.sped_consulta_status_documento_form').id,
            'type': 'ir.actions.act_window',
            'context': {
                'default_empresa_id': self.empresa_id.id,
                'default_purchase_order_id': self.id,
            },
            'target': 'new'
        }
