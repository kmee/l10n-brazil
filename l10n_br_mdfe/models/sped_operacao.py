# Copyright 2018 KMEE INFORMATICA LTDA, Grupo Zenir
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from odoo import fields, models

from ..constants.mdfe import EMITTER_TYPE, TRANSPORT_MODALITY, TRANSPORTER_TYPE


class SpedOperacao(models.Model):

    _inherit = 'l10n_br_fiscal.operation'

    emitter_type = fields.Selection(
        selection=EMITTER_TYPE,
        string='Emitter type',
    )

    transporter_type = fields.Selection(
        selection=TRANSPORTER_TYPE,
        string='Transporter type'
    )
    transport_modality = fields.Selection(
        selection=TRANSPORT_MODALITY,
        string='Modality',
    )
