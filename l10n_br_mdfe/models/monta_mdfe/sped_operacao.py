# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from odoo import models


class SpedOperacao(models.Model):
    _inherit = 'l10n_br_fiscal.operation'

    def monta_mdfe(self):
        self.ensure_one()
        return
