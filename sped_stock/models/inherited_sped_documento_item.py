# -*- coding: utf-8 -*-
# Copyright 2017 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import fields, models


class SpedStockDocumentoItem(models.Model):
    _inherit = 'sped.documento.item'

    stock_move_id = fields.Many2one(
        comodel_name='stock.move',
        string='Movimento de Estoque',
        copy=False,
    )
