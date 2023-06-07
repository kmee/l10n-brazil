# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from odoo import fields, models

from ..constants.mdfe import EMISSION_TYPE_MDFE, MDFE_ENVIRONMENT


class SpedEmpresa(models.Model):

    _inherit = 'res.company'

    environment_mdfe = fields.Selection(
        selection=MDFE_ENVIRONMENT,
        string='Ambiente MDF-E'
    )
    emission_type_mdfe = fields.Selection(
        selection=EMISSION_TYPE_MDFE,
        string='Tipo de emissão MDF-E'
    )
    serie_mdfe_production = fields.Char(
        selection='Série em produção',
        default='1'
    )
    serie_mdfe_homologation = fields.Char(
        string='Série em homologação',
        default='100'
    )
    serie_mdfe_production_contingency = fields.Char(
        string='Série em homologação',
        default='900'
    )
    serie_mdfe_contingency_homologation = fields.Char(
        string='Série em produção',
        default='999'
    )
    emission_type_mdfe_contingency = fields.Selection(
        selection=EMISSION_TYPE_MDFE,
        string='Tipo de emissão MDF-E contingência'
    )
