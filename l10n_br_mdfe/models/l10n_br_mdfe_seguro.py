# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from odoo import fields, models

from ..constants.mdfe import RESPONSIBLE_INSURANCE


class L10nBrMdfeSeguro(models.Model):

    _name = 'l10n_br.mdfe.insurance'
    _description = 'Mdfe Insurance'

    document_id = fields.Many2one(
        comodel_name='l10n_br_fiscal.document'
    )

    responsible_insurance = fields.Selection(
        selection=RESPONSIBLE_INSURANCE,
        string='Responsible',
    )
    responsible_cnpj_cpf = fields.Char(
        string='CNPJ/CPF',
        index=True,
        store=True,
    )
    insurer_id = fields.Many2one(
        comodel_name='res.partner',
        string='Insurer',
    )
    name = fields.Char(
        string='Insurer name',
        related='insurer_id.display_name',
        store=True,
    )
    cnpj_cpf = fields.Char(
        string='CNPJ/CPF',
        index=True,
        related='insurer_id.cnpj_cpf',
        store=True,
    )
    policy_number = fields.Char(
        string='Policy number',
    )
    annotation_ids = fields.One2many(
        comodel_name='l10n_br.mdfe.insurance.annotation',
        inverse_name='insurance_id'
    )
    # TODO: Validar o CNPJ/ CPF
    # TODO: Formatar o CNPJ / CPF
