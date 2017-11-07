# -*- coding: utf-8 -*-
#
# Copyright 2017 KMEE INFORMATICA LTDA
#    Aristides Caldeira <aristides.caldeira@kmee.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from odoo import api, fields, models


class FinanConta(models.Model):
    _name = 'finan.conta'
    _description = 'Conta Financeira'
    _rec_name = 'nome_completo'
    _order = 'codigo, nome_completo'

    codigo = fields.Char(
        string='Código',
        size=20,
        index=True,
        required=True,
    )
    nome = fields.Char(
        string='Nome',
        size=60,
        index=True,
        required=True,
    )
    conta_superior_id = fields.Many2one(
        comodel_name='finan.conta',
        string='Conta superior',
        ondelete='cascade',
        index=True,
    )
    conta_relacionada_ids = fields.One2many(
        comodel_name='finan.conta',
        inverse_name='conta_superior_id',
        string='Contas relacionadas',
    )
    nivel = fields.Integer(
        string='Nível',
        compute='_compute_conta',
        store=True,
        index=True,
    )
    eh_redutora = fields.Boolean(
        string='É redutora?',
        compute='_compute_conta',
        store=True,
    )
    sinal = fields.Integer(
        string='Sinal',
        compute='_compute_conta',
        store=True,
    )
    nome_completo = fields.Char(
        string='Conta',
        size=500,
        compute='_compute_conta',
        store=True,
    )
    tipo = fields.Selection(
        selection=[
            ('A', 'Analítica'),
            ('S', 'Sintética')
        ],
        string='Tipo',
        compute='_compute_conta',
        store=True,
        index=True,
    )

    def _compute_nivel(self):
        self.ensure_one()

        nivel = 1
        if self.conta_superior_id:
            nivel += self.conta_superior_id._compute_nivel()

        return nivel

    def _compute_nome_completo(self):
        self.ensure_one()

        nome = self.nome

        if self.conta_superior_id:
            nome = self.conta_superior_id._compute_nome_completo() + \
                ' / ' + nome

        return nome

    @api.depends('conta_superior_id', 'codigo', 'nome',
                 'conta_relacionada_ids.conta_superior_id')
    def _compute_conta(self):
        for conta in self:
            conta.nivel = conta._compute_nivel()

            if conta.nome and \
                    conta.nome.startswith('(-)') or \
                    conta.nome.startswith('( - )'):
                conta.eh_redutora = True
                conta.sinal = -1
            else:
                conta.eh_redutora = False
                conta.sinal = 1

            if len(conta.conta_relacionada_ids) > 0:
                conta.tipo = 'S'
            else:
                conta.tipo = 'A'

            if conta.codigo and conta.nome:
                conta.nome_completo = conta.codigo + ' - ' + \
                    conta._compute_nome_completo()

    def ajusta_agrupamento(self):
        sql = "update finan_conta set conta_superior_id = null, tipo='A';"
        self.env.cr.execute(sql)

        sql = '''
        update finan_conta set
            conta_superior_id = %(conta_id)s

        where
            id != %(conta_id)s
            and codigo like %(conta_codigo)s;
        '''

        for conta in self.search([]):
            filtros = {
                'conta_id': conta.id,
                'conta_codigo': conta.codigo + '%',
            }
            self.env.cr.execute(sql, filtros)

        sql = """
        update finan_conta set
            tipo='S'

        where
            id in (select distinct conta_superior_id from finan_conta);
        """
        self.env.cr.execute(sql)

    def recria_finan_conta_arvore(self):
        self.ajusta_agrupamento()

        SQL_RECRIA_FINAN_CONTA_ARVORE = '''
        delete from finan_conta_arvore;

        insert into finan_conta_arvore (
          id,
          conta_relacionada_id,
          conta_superior_id,
          nivel
        )
        select
           row_number() over() as id,
           conta_relacionada_id,
           conta_superior_id,
           nivel
        from
            finan_conta_arvore_view
        order by
            conta_relacionada_id,
            conta_superior_id;
        '''
        self.env.cr.execute(SQL_RECRIA_FINAN_CONTA_ARVORE)

    @api.model
    def create(self, vals):
        res = super(FinanConta, self).create(vals)

        self.recria_finan_conta_arvore()

        return res

    @api.multi
    def write(self, vals):
        res = super(FinanConta, self).write(vals)

        self.recria_finan_conta_arvore()

        return res

    @api.multi
    def unlink(self):
        res = super(FinanConta, self).unlink()

        self.recria_finan_conta_arvore()

        return res
