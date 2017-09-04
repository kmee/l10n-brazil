# -*- coding: utf-8 -*-
# Copyright 2017 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class SpedParticipante(models.Model):

    _inherit = 'sped.participante'

    credit_limit = fields.Float(
        string=u'Limite de Crédito',
        digits=(16, 2),
    )
    available_credit_limit = fields.Float(
        string=u'Limite de Crédito Disponível',
        digits=(16, 2),
        compute='_compute_credit',
        store=True,
    )
    credit = fields.Float(
        string=u'Saldo devedor',
        digits=(16, 2),
        compute='_compute_credit',
        store=True,
    )

    @api.depends('credit_limit')
    def _compute_credit(self):
        for participante in self:
            credito = 0.00
            contas = self.env['financial.move'].search([
                ('participante_id', '=',
                 participante.env.context.get('params').get('id') or
                 participante.id
                 ),
                ('type', '=', '2receive'),
                ('state', '=', 'open'),
            ])
            for conta in contas:
                credito += conta.amount_residual
            participante.credit = credito
            participante.available_credit_limit = \
                participante.credit_limit - credito
