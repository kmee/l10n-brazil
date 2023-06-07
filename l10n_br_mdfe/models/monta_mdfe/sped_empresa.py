# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from odoo import models


class SpedEmpresa(models.Model):
    _inherit = 'res.company'

    def monta_mdfe(self):
        self.ensure_one()
        return
