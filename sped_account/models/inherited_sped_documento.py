# -*- coding: utf-8 -*-
#
# Copyright 2016 Taŭga Tecnologia
#   Aristides Caldeira <aristides.caldeira@tauga.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from __future__ import division, print_function, unicode_literals

from odoo import api, fields, models


class SpedDocumento(models.Model):
    _inherit = 'sped.documento'

    journal_id = fields.Many2one(
        comodel_name='account.journal',
        string='Diário',
        domain=[('is_brazilian_journal', '=', True)],
    )
    move_template_id = fields.Many2one(
        comodel_name='sped.account.move.template',
        string='Modelo de partidas dobradas',
    )
    account_move_id = fields.Many2one(
        comodel_name='account.move',
        string='Lançamento contábil',
        ondelete='restrict',
    )
    account_move_line_ids = fields.One2many(
        comodel_name='account.move.line',
        inverse_name='move_id',
        string='Partidas do lançamento contábil',
        related='account_move_id.line_ids',
    )

    def executa_antes_autorizar(self):
        super(SpedDocumento, self).executa_antes_autorizar()
        self.gera_account_move()

    def gera_account_move(self):
        for documento in self:
            dados = {
                'sped_documento_id': documento.id,
                'journal_id': documento.journal_id.id,
                'ref': documento.descricao,
                'sped_participante_id': documento.participante_id.id,
                'sped_empresa_id': documento.empresa_id.id,
                'partner_id': documento.participante_id.partner_id.id,
                'company_id': documento.empresa_id.company_id.id,
                'date': documento.data_entrada_saida,
            }

            if documento.account_move_id:
                if documento.account_move_id.state != 'draft':
                    # raise
                    continue
                account_move = documento.account_move_id
                account_move.write(dados)
            else:
                account_move = self.env['account.move'].create(dados)
                documento.account_move_id = account_move

            line_ids = [(5, 0, {})]

            documento.item_ids.gera_account_move_line(account_move,
                                                      documento.move_template_id, line_ids)

            if len(line_ids):
                account_move.write({'line_ids': line_ids})

    @api.depends('modelo', 'emissao')
    def _compute_permite_alteracao(self):
        super(SpedDocumento, self)._compute_permite_alteracao()

        for documento in self:
            if not documento.permite_alteracao:
                continue

            if documento.account_move_id:
                documento.permite_alteracao = False

    @api.depends('modelo', 'emissao')
    def _compute_permite_cancelamento(self):
        super(SpedDocumento, self)._compute_permite_cancelamento()

        for documento in self:
            if not documento.permite_cancelamento:
                continue

            if documento.account_move_id:
                documento.permite_cancelamento = False
