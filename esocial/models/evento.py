# -*- coding: utf-8 -*-
#
# Copyright 2017 KMEE
#   Wagner Pereira <wagner.pereira@kmee.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from odoo import api, fields, models, _


class Eventos(models.Model):
    _name = 'esocial.evento'
    _description = 'Tabela de Eventos do e-Social'
    _order = 'data_hora_protocolo desc, name'

    evento = fields.Char(
        size=6,
        string='Codigo do Evento',
        required=True,
    )
    empresa_id = fields.Many2one(
        string='Empresa',
        comodel_name='sped.empresa',
        ondelete="restrict",
    )
    lote_id = fields.Many2one(
        string='Lote',
        comodel_name='esocial.lote',
        ondelete="restrict",
    )
    data_hora_protocolo = fields.Datetime(
        string='Data/Hora Protocolo',
    )
    protocolo = fields.Char(
        string='Protocolo de Entrega',
    )
    data_hora_recibo = fields.Datetime(
        string='Data/Hora Recibo',
    )
    recibo = fields.Char(
        string='Recibo de Entrega',
    )
    name = fields.Char(
        compute='_compute_name',
        store=True,
    )
    state = fields.Selection(
        string='Situação',
        selection=[
            ('rascunho', 'Rascunho'),
            ('transmitido', 'Transmitido'),
            ('processado', 'Processado'),
        ]
    )

    @api.onchange('evento',
                  'empresa_id',
                  'data_hora_protocolo',
                  'data_hora_recibo')
    def _compute_name(self):
        for evento in self:
            data_hora = evento.data_hora_recibo \
                if evento.data_hora_recibo else evento.data_hora_protocolo
            evento.name = "%s - %s - %s" % \
                          (evento.evento,
                           evento.empresa_id.name,
                           fields.Date.to_string(data_hora)
                           )
