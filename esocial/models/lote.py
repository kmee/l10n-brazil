# -*- coding: utf-8 -*-
#
# Copyright 2017 KMEE
#   Wagner Pereira <wagner.pereira@kmee.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from odoo import api, fields, models, _


class Lotes(models.Model):
    _name = 'esocial.lote'
    _description = 'Tabela de Lotes de Comunicação com o e-Social'
    _order = 'data_hora_protocolo desc, name'

    lote = fields.Char(
        string='Número',
        required=True,
    )
    empresa_id = fields.Many2one(
        string='Empresa',
        comodel_name='sped.empresa',
        ondelete="restrict",
    )
    evento_ids = fields.One2many(
        string='Eventos',
        comodel_name='esocial.evento',
        inverse_name='lote_id',
    )
    eventos = fields.Integer(
        string='Eventos',
        compute='_compute_eventos',
    )
    data_hora_protocolo = fields.Datetime(
        string='Data/Hora Protocolo',
    )
    protocolo = fields.Char(
        string='Protocolo de Entrega',
    )
    tempo_estimado = fields.Char(   # <tempoEstimadoConclusao>
        string='Tempo Estimado de Conclusão do Lote',
    )
    data_hora_recibo = fields.Datetime(
        string='Data/Hora Recibo'
    )
    recibo = fields.Char(
        string='Recibo de Entrega',
    )
    name = fields.Char(
        compute='_compute_name',
        store=True,
    )
    arquivo_envio = fields.Binary(
        string='Arquivo XML',
    )
    arquivo_retorno = fields.Binary(
        string='Arquivo XML',
    )
    state = fields.Selection(
        string='Situação',
        selection=[
            ('rascunho', 'Rascunho'),
            ('transmitido', 'Transmitido'),
            ('processado', 'Processado'),
        ]
    )

    @api.onchange('lote',
                  'empresa_id',
                  'data_hora_protocolo',
                  'data_hora_recibo')
    def _compute_name(self):
        for lote in self:
            data_hora = lote.data_hora_recibo \
                if lote.data_hora_recibo else lote.data_hora_protocolo
            lote.name = "%s - %s - %s" % \
                        (lote.lote,
                         lote.empresa_id.name,
                         fields.Date.to_string(data_hora)
                         )

    @api.depends('evento_ids')
    def _compute_eventos(self):
        for lote in self:
            lote.eventos = len(lote.evento_ids)