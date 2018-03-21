# -*- coding: utf-8 -*-
#
# Copyright 2018 KMEE INFORMATICA LTDA
#   Luis Felipe Mileo <mileo@kmee.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from __future__ import division, print_function, unicode_literals

from odoo import api, models, _


class SpedDocumentoDevolucao(models.TransientModel):
    _inherit = 'sped.documento.devolucao'

    @api.multi
    def _criar_devolucao(self):
        doc = super(SpedDocumentoDevolucao, self)._criar_devolucao()
        doc.gera_estoque()
        return doc

