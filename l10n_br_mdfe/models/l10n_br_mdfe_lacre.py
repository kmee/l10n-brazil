# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from odoo import fields, models


class L10n_brMdfeLacre(models.Model):

    _name = 'l10n_br.mdfe.seal'
    _description = 'Lacre do MDF-E'

    name = fields.Char()
    document_id = fields.Many2one(
        comodel_name='l10n_br_fiscal.document'
    )
