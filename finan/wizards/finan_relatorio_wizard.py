# -*- coding: utf-8 -*-
#
# Copyright 2017 KMEE INFORMATICA LTDA
#    Aristides Caldeira <aristides.caldeira@kmee.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from datetime import datetime
from odoo import fields, models, api
from ..constantes import (
    FINAN_DIVIDA,
    FINAN_DIVIDA_A_RECEBER,
    FINAN_SITUACAO_DIVIDA,
    FINAN_SITUACAO_DIVIDA_VENCIDO,
    FINAN_SITUACAO_DIVIDA_SIMPLES,
    FINAN_SITUACAO_DIVIDA_SIMPLES_ABERTO,
)


class FinanRelatorioWizard(models.TransientModel):
    _name = 'finan.relatorio.wizard'
    _description = 'Relatórios Financeiros - Wizard'

    empresa_id = fields.Many2one(
        comodel_name='sped.empresa',
        string='Empresa',
        default=lambda self:
            self.env['sped.empresa']._empresa_ativa('sped.empresa'),
    )
    periodo = fields.Selection(
        string='Período em',
        default='meses',
        selection=[
            ('meses', 'Meses'),
            # ('semanas', 'Semanas'),
            ('dias', 'Dias'),
        ],
    )
    data_periodo = fields.Selection(
        selection=[
            ('data_vencimento_util', 'Período Previsto'),
            ('data_credito_debito', 'Período Realizado')
        ],
        string='Período',
        default='data_vencimento_util',
    )
    data_inicial = fields.Date(
        default=datetime.now().strftime('%Y-%m-01'),
    )
    data_final = fields.Date(
        default=datetime.now().strftime('%Y-12-31'),
    )
    group_by = fields.Selection(
        string='Agrupamento',
        selection=[
            ('data_vencimento_util', 'Vencimento'),
            ('participante_id', 'Parceiro'),
        ],
        default='data_vencimento_util',
    )
    participante_ids = fields.Many2many(
        comodel_name='sped.participante',
        relation='finan_relatorio_participante',
        column1='wizard_id',
        column2='participante_id',
        string='Parceiros',
    )
    tipo_divida = fields.Selection(
        selection=FINAN_DIVIDA,
        string='Tipo',
        default=FINAN_DIVIDA_A_RECEBER,
    )
    situacao_divida = fields.Selection(
        string='Situação',
        selection=FINAN_SITUACAO_DIVIDA,
        default=FINAN_SITUACAO_DIVIDA_VENCIDO,
    )
    situacao_divida_simples = fields.Selection(
        string='Situação',
        selection=FINAN_SITUACAO_DIVIDA_SIMPLES,
        default=FINAN_SITUACAO_DIVIDA_SIMPLES_ABERTO,
    )

    @api.multi
    def gera_relatorio_fluxo_caixa(self):
        self.ensure_one()

        return self.env['ir.actions.report']._get_report_from_name(
            'finan.finan_relatorio_fluxo_caixa').report_action(
            self.id,
        )

    @api.multi
    def gera_relatorio_divida(self):
        self.ensure_one()

        return self.env['ir.actions.report']._get_report_from_name(
            'finan.finan_relatorio_divida').report_action(
            self.id,
        )
