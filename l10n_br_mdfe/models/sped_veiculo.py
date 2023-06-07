# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from odoo import fields, models

from ..constants.mdfe import BODY_TYPE, WHEELED_TYPE


class SpedVeiculo(models.Model):

    _inherit = 'l10n_br_delivery.carrier.vehicle'

    code = fields.Char(
        string='Code'
    )
    ciot = fields.Char(
        string='CIOT type',
        help='Também Conhecido como conta frete',
    )
    wheeled_type = fields.Selection(
        selection=WHEELED_TYPE,
        string='Wheeled',
    )
    body_type = fields.Selection(
        selection=BODY_TYPE,
        string='Body type',
    )
    tare_kg = fields.Float(
        string='Tare (kg)'
    )
    capacity_kg = fields.Float(
        string='Capacity (kg)',
    )
    capacity_m3 = fields.Float(
        string='Capacity (m³)'
    )

    def name_get(self):
        res = []
        for record in self:
            name = ''
            if record.code:
                name = '['
                name += record.code
                name += '] '
            name += record.placa
            res.append((record.id, name))
        return res
