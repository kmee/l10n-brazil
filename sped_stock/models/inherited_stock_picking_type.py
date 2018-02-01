# -*- coding: utf-8 -*-
# Copyright 2017 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from odoo import models, fields


class StockPickingType(models.Model):
    _inherit = 'stock.picking.type'

    operacao_ids = fields.Many2many(
        comodel_name='sped.operacao',
        relation='stock_picking_type_operacao_rel',
    )

