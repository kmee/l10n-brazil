# -*- coding: utf-8 -*-
# Copyright 2017 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import fields, models


class SpedDocumentoItem(models.Model):
    _inherit = 'sped.documento.item'

    sale_order_line_id = fields.Many2one(
        comodel_name='sale.order.line',
        string='Item do pedido de venda',
        ondelete='restrict',
        copy=False,
    )
