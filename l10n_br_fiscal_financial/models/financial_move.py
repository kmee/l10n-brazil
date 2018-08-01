# -*- coding: utf-8 -*-
#
# Copyright 2017 KMEE INFORMATICA LTDA
#   Aristides Caldeira <aristides.caldeira@kmee.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from __future__ import division, print_function, unicode_literals


from openerp import api, fields, models


class FinancialMove(models.Model):
    _inherit = b'financial.move'

    sped_documento_duplicata_id = fields.Many2one(
        string="Financial move",
        comodel_name="sped.documento.duplicata",
    )
    sped_forma_pagamento_id = fields.Many2one(
        string='Forma de pagamento',
        comodel_name='sped.forma.pagamento',
    )
