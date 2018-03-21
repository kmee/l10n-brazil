# -*- coding: utf-8 -*-
# Copyright 2017 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from odoo import api, fields, models


class InventoryLine(models.Model):
    _inherit = b'stock.inventory.line'

    vr_unitario_custo = fields.Float(
        string='Valor Custo Unitário',
    )

    vr_total_custo = fields.Float(
        string='Valor Custo Total',
    )
