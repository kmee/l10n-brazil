# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from mdfelib.v3_00.mdfe import lacresType
from odoo import models


class L10n_brMdfeLacre(models.Model):
    _inherit = 'l10n_br.mdfe.seal'

    def monta_mdfe(self):
        seals = []

        for record in self:
            seals.append(
                lacresType(nLacre=record.name)
            )
        return seals
