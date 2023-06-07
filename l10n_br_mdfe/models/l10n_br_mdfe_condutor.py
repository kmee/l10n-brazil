# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from erpbrasil.base import misc
from odoo import fields, models


class L10nBrMdfeCondutor(models.Model):
    _name = 'l10n_br.mdfe.conductor'
    _description = 'Condutor MDF-E'

    def _compute_cpf(self):
        for record in self:
            if record.cpf:
                record.cpj_numbers = misc.punctuation_rm(record.cpf)

    document_id = fields.Many2one(
        comodel_name='coductor_ids'
    )
    conductor_id = fields.Many2one(
        comodel_name='res.partner',
        string='Conductor',
    )
    name = fields.Char(
        string='Name',
        related='conductor_id.display_name',
        index=True,
        store=True,
    )
    cpf = fields.Char(
        string='CPF',
        index=True,
        store=True,
        related='conductor_id.cnpj_cpf'
    )
    cpf_numbers = fields.Char(
        string='CPF (only numbers)',
        compute='_compute_cpf',
        store=True,
        index=True,
    )
