# -*- coding: utf-8 -*-
#
# Copyright 2017 KMEE INFORMATICA LTDA
#   Luis Felipe Miléo <mileo@kmee.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from __future__ import division, print_function, unicode_literals

from odoo import models, fields


class ResUsers(models.Model):
    _inherit = 'res.users'

    configuracoes_sat_cfe = fields.One2many(
        string=u"Caixa Ponto de Venda",
        comodel_name="pdv.config",
        inverse_name="vendedor"
    )
