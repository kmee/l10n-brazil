# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from odoo import fields, models


class L10nBrMdfeSeguroAverbacao(models.Model):

    _name = 'l10n_br.mdfe.insurance.annotation'
    _description = 'Mdfe Seguro Averbação'
    name = fields.Char(
        string='Numero da averbação',
    )
    insurance_id = fields.Many2one(
        comodel_name='l10n_br.mdfe.insurance',

    )
    document_id = fields.Many2one(
        comodel_name='l10n_br_fiscal.document',
        related='insurance_id.document_id',
        store=True,
    )
