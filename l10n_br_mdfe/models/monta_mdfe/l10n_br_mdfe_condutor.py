# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from erpbrasil.base import misc
from mdfelib.v3_00 import mdfeModalRodoviario as rodo3
from odoo import models


class L10nBrMdfeCondutor(models.Model):

    _inherit = 'l10n_br.mdfe.conductor'

    def monta_mdfe(self):
        conductors = []
        for record in self:
            conductors.append(
                rodo3.condutorType(
                    xNome=record.name,
                    CPF=misc.punctuation_rm(record.cpf),
                )
            )
        return conductors
