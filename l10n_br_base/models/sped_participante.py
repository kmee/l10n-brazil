# -*- coding: utf-8 -*-
#
# Copyright 2016 Taŭga Tecnologia
#   Aristides Caldeira <aristides.caldeira@tauga.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#
from odoo import api, fields, models, _


class SpedParticipante(models.Model):
    _name = b'sped.participante'
    _description = 'Participantes'
    _inherits = {'res.partner': 'partner_id'}

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string='Partner original',
        ondelete='restrict',
        required=True,
    )

    @api.multi
    def name_get(self):
        res = []
        for record in self:
            res.append((record.id, record.partner_id.name_get()[0][1]))
        return res

    @api.model
    def create(self, vals):
        participante = super(SpedParticipante, self.with_context(
            create_sped_participante=True)).create(vals)
        return participante
