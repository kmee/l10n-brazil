# -*- coding: utf-8 -*-
#
# Copyright 2017 KMEE
#   Wagner Pereira <wagner.pereira@kmee.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from odoo import api, fields, models, _

ESOCIAL_SITUACAO = [
    ('inativo', 'Inativo'),
    ('ativo', 'Ativo'),
    ('desativado', 'Desativado'),
]

ESOCIAL_AMBIENTE = [
    ('1', 'Produção'),
    ('2', 'Pré-Produção - dados reais'),
    ('3', 'Pré-Produção - dados fictícios'),
    ('6', 'Homologação'),
    ('7', 'Validação'),
    ('8', 'Testes'),
    ('9', 'Desenvolvimento'),
]


class SpedEmpresa(models.Model):
    _name = 'sped.empresa'
    _description = 'Tabela de Eventos do e-Social'
    _inherit = 'sped.empresa'

    esocial_situacao = fields.Selection(
        string='Situação no e-Social',
        selection=ESOCIAL_SITUACAO,
        default='inativo',
    )
    esocial_ambiente = fields.Selection(
        string='Ambiente',
        selection=ESOCIAL_AMBIENTE,
        default='4',
        required=True,
    )
    lote_ids = fields.One2many(
        string='Lotes',
        comodel_name='esocial.lote',
        inverse_name='empresa_id',
    )
    evento_ids = fields.One2many(
        string='Eventos',
        comodel_name='esocial.evento',
        inverse_name='empresa_id',
    )
    lotes = fields.Integer(
        string='Lotes',
        compute='_compute_lotes',
    )
    eventos = fields.Integer(
        string='Eventos',
        compute='_compute_eventos',
    )
    natureza_juridica_id = fields.Many2one(
        string='Natureza Jurídica',
        comodel_name='esocial.natureza_juridica',
        inverse_name='empresa_ids',
        ondelete='restrict',
    )

    @api.depends('lote_ids')
    def _compute_lotes(self):
        for empresa in self:
            empresa.lotes = len(empresa.lote_ids)

    @api.depends('evento_ids')
    def _compute_eventos(self):
        for empresa in self:
            empresa.eventos = len(empresa.evento_ids)

    def ativa_esocial(self):
        for empresa in self:

            #
            # Incluir aqui envio de evento S-1000 - ativação
            #

            empresa.esocial_situacao = 'ativo'

    def desativa_esocial(self):
        for empresa in self:

            #
            # Incluir aqui envio do evento S-1000 - desativação

            empresa.esocial_situacao = 'desativado'
