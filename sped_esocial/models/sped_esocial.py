# -*- coding: utf-8 -*-
# Copyright 2018 ABGF
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import api, fields, models
from openerp.exceptions import ValidationError
from datetime import datetime


class SpedEsocial(models.Model):
    _name = 'sped.esocial'
    _description = 'Eventos Periódicos e-Social'
    _rec_name = 'nome'
    _order = "nome DESC"
    _sql_constraints = [
        ('periodo_company_unique', 'unique(periodo_id, company_id)', 'Este período já existe para esta empresa !')
    ]

    nome = fields.Char(
        string='Nome',
        compute='_compute_nome',
        store=True,
    )
    nome_readonly = fields.Char(
        string='Nome',
        compute='_compute_readonly',
    )
    periodo_id = fields.Many2one(
        string='Período',
        comodel_name='account.period',
    )
    periodo_id_readonly = fields.Many2one(
        string='Período',
        comodel_name='account.period',
        compute='_compute_readonly',
    )
    date_start = fields.Date(
        string='Início do Período',
        related='periodo_id.date_start',
        store=True,
    )
    company_id = fields.Many2one(
        string='Empresa',
        comodel_name='res.company',
    )
    company_id_readonly = fields.Many2one(
        string='Empresa',
        comodel_name='res.company',
        compute='_compute_readonly',
    )
    situacao = fields.Selection(
        string='Situação',
        selection=[
            ('1', 'Aberto'),
            ('2', 'Precisa Retificar'),
            ('3', 'Fechado')
        ],
        default='1',
        #compute='_compute_situacao',
        store=True,
    )

    # Controle dos registros S-1000
    empregador_ids = fields.Many2many(
        string='Empregadores',
        comodel_name='sped.empregador',
    )
    necessita_s1000 = fields.Boolean(
        string='Necessita S-1000(s)',
        compute='compute_necessita_s1000',
    )

    #
    # Calcula se é necessário criar algum registro S-1000
    #
    @api.depends('empregador_ids.situacao_esocial')
    def compute_necessita_s1000(self):
        for esocial in self:
            necessita_s1000 = False
            for empregador in esocial.empregador_ids:
                if empregador.situacao_esocial in ['2']:
                    necessita_s1000 = True
            esocial.necessita_s1000 = necessita_s1000

    @api.multi
    def importar_empregador(self):
        self.ensure_one()

        empregadores = self.env['sped.empregador'].search([
            ('company_id', '=', self.company_id.id),
        ])
        for empregador in empregadores:
            if empregador.id not in self.empregador_ids.ids:
                if empregador.situacao_esocial != '9':
                    self.empregador_ids = [(4, empregador.id)]

    # Cria o registro S-1000
    @api.multi
    def criar_s1000(self):
        self.ensure_one()
        for empregador in self.empregador_ids:
            empregador.atualizar_esocial()

    #
    # Controle dos registros S-1005
    #
    estabelecimento_ids = fields.Many2many(
        string='Estabelecimentos',
        comodel_name='sped.estabelecimentos',
    )
    necessita_s1005 = fields.Boolean(
        string='Necessita S-1005(s)',
        compute='compute_necessita_s1005',
    )

    # Calcula se é necessário criar algum registro S-1005
    @api.depends('estabelecimento_ids.situacao_esocial')
    def compute_necessita_s1005(self):
        for esocial in self:
            necessita_s1005 = False
            for estabelecimento in esocial.estabelecimento_ids:
                if estabelecimento.situacao_esocial in ['2']:
                    necessita_s1005 = True
            esocial.necessita_s1005 = necessita_s1005

    @api.multi
    def importar_estabelecimentos(self):
        self.ensure_one()

        estabelecimentos = self.env['sped.estabelecimentos'].search([
            ('company_id', '=', self.company_id.id),
        ])
        for estabelecimento in estabelecimentos:
            if estabelecimento.id not in self.estabelecimento_ids.ids:
                if estabelecimento.situacao_esocial != '9':
                    self.estabelecimento_ids = [(4, estabelecimento.id)]

    # Cria os registros S-1005
    @api.multi
    def criar_s1005(self):
        self.ensure_one()
        for estabelecimento in self.estabelecimento_ids:
            estabelecimento.atualizar_esocial()

    # Controle de registros S-1010
    rubrica_ids = fields.Many2many(
        string='Rubricas',
        comodel_name='sped.esocial.rubrica',
        inverse_name='esocial_id',
    )
    necessita_s1010 = fields.Boolean(
        string='Necessita S-1010(s)',
        compute='compute_necessita_s1010',
    )

    # Calcula se é necessário criar algum registro S-1010
    @api.depends('rubrica_ids.situacao_esocial')
    def compute_necessita_s1010(self):
        for esocial in self:
            necessita_s1010 = False
            for rubrica in esocial.rubrica_ids:
                if rubrica.situacao_esocial in ['2']:
                    necessita_s1010 = True
            esocial.necessita_s1010 = necessita_s1010

    @api.multi
    def importar_rubricas(self):
        self.ensure_one()

        # Roda todas as Rubricas que possuem o campo nat_rubr definido (Natureza da Rubrica)
        rubricas = self.env['hr.salary.rule'].search([
            ('nat_rubr', '!=', False),
        ])
        for rubrica in rubricas:

            # Procura o registro intermediário S-1010 correspondente
            s1010 = self.env['sped.esocial.rubrica'].search([
                ('company_id', '=', self.company_id.id),
                ('rubrica_id', '=', rubrica.id),
            ])
            if not s1010:

                # Cria o registro intermediário
                vals = {
                    'company_id': self.company_id.id,
                    'rubrica_id': rubrica.id,
                }
                s1010 = self.env['sped.esocial.rubrica'].create(vals)
                self.rubrica_ids = [(4, s1010.id)]
            else:

                # Adiciona no período o link para o registro S-1010 (se não estiver)
                if s1010.id not in self.rubrica_ids.ids:
                    self.rubrica_ids = [(4, s1010.id)]

            # Gera o registro de transmissão (se for necessário)
            s1010.gerar_registro()

    @api.multi
    def criar_s1010(self):
        self.ensure_one()
        for rubrica in self.rubrica_ids:
            rubrica.gerar_registro()

    # Controle de registros S-1020
    lotacao_ids = fields.Many2many(
        string='Lotações Tributárias',
        comodel_name='sped.esocial.lotacao',
    )
    necessita_s1020 = fields.Boolean(
        string='Necessita S-1020',
        compute='compute_necessita_s1020',
    )

    # Calcula se é necessário criar algum registro S-1020
    @api.depends('lotacao_ids.situacao_esocial')
    def compute_necessita_s1020(self):
        for esocial in self:
            necessita_s1020 = False
            for lotacao in esocial.lotacao_ids:
                if lotacao.situacao_esocial in ['2']:
                    necessita_s1020 = True
            esocial.necessita_s1020 = necessita_s1020

    @api.multi
    def importar_lotacoes(self):
        self.ensure_one()

        lotacoes = self.env['sped.esocial.lotacao'].search([
            ('company_id', '=', self.company_id.id),
        ])
        for lotacao in lotacoes:
            if lotacao.id not in self.lotacao_ids.ids:
                if lotacao.situacao_esocial != '9':
                    self.lotacao_ids = [(4, lotacao.id)]

    @api.multi
    def criar_s1020(self):
        self.ensure_one()
        for lotacao in self.lotacao_ids:
            lotacao.gerar_registro()

    # Calcula se é necessário criar algum registro S-1020
    @api.depends('lotacao_ids.situacao_esocial')
    def compute_necessita_s1020(self):
        for esocial in self:
            necessita_s1020 = False
            for lotacao in esocial.lotacao_ids:
                if lotacao.situacao_esocial in ['2']:
                    necessita_s1020 = True
            esocial.necessita_s1020 = necessita_s1020

    # Controle de registros S-1030
    cargo_ids = fields.Many2many(
        string='Cargos',
        comodel_name='sped.esocial.cargo',
    )
    necessita_s1030 = fields.Boolean(
        string='Necessita S-1030',
        compute='compute_necessita_s1030',
    )

    # Calcula se é necessário criar algum registro S-1030
    @api.depends('cargo_ids.situacao_esocial')
    def compute_necessita_s1030(self):
        for esocial in self:
            necessita_s1030 = False
            for cargo in esocial.cargo_ids:
                if cargo.situacao_esocial in ['2']:
                    necessita_s1030 = True
            esocial.necessita_s1030 = necessita_s1030

    @api.multi
    def importar_cargos(self):
        self.ensure_one()

        cargos = self.env['sped.esocial.cargo'].search([
            ('company_id', '=', self.company_id.id),
        ])
        for cargo in cargos:
            if cargo.id not in self.cargo_ids.ids:
                if cargo.situacao_esocial != '9':
                    self.cargo_ids = [(4, cargo.id)]

    # Criar registros S-1030
    @api.multi
    def criar_s1030(self):
        self.ensure_one()
        for cargo in self.cargo_ids:
            cargo.gerar_registro()

    # Controle de registros S-1050
    turno_trabalho_ids = fields.Many2many(
        string='Turnos de Trabalho',
        comodel_name='sped.hr.turnos.trabalho',
    )
    necessita_s1050 = fields.Boolean(
        string='Necessita S-1050',
        compute='compute_necessita_s1050',
    )

    # Calcula se é necessário criar algum registro S-1050
    @api.depends('turno_trabalho_ids.situacao_esocial')
    def compute_necessita_s1050(self):
        for esocial in self:
            necessita_s1050 = False
            for turno in esocial.turno_trabalho_ids:
                if turno.situacao_esocial in ['2']:
                    necessita_s1050 = True
            esocial.necessita_s1050 = necessita_s1050

    @api.multi
    def importar_turnos_trabalho(self):
        self.ensure_one()

        turnos_trabalho_ids = self.env['sped.hr.turnos.trabalho'].search([
            ('company_id', '=', self.company_id.id),
        ])

        for turno_trabalho in turnos_trabalho_ids:
            if turno_trabalho.id not in self.turno_trabalho_ids.ids:
                if turno_trabalho.situacao_esocial != '9':
                    self.turno_trabalho_ids = [(4, turno_trabalho.id)]

    # Criar registros S-1050
    @api.multi
    def criar_s1050(self):
        self.ensure_one()
        for turno in self.turno_trabalho_ids:
            turno.gerar_registro()

    # Controle de registros S-1200
    remuneracao_ids = fields.Many2many(
        string='Remuneração de Trabalhador',
        comodel_name='sped.esocial.remuneracao',
    )

    @api.multi
    def importar_remuneracoes(self):
        self.ensure_one()

        # Buscar Trabalhadores
        trabalhadores = self.env['hr.employee'].search([])

        periodo = self.periodo_id
        matriz  = self.company_id
        empresas = self.env['res.company'].search([('matriz', '=', matriz.id)]).ids
        if matriz.id not in empresas:
            empresas.append(matriz.id)

        # separa somente os trabalhadores com contrato válido neste período e nesta empresa matriz
        # trabalhadores_com_contrato = []
        for trabalhador in trabalhadores:

            # Localiza os contratos válidos deste trabalhador
            domain = [
                ('employee_id', '=', trabalhador.id),
                ('company_id', 'in', empresas),
                ('date_start', '<=', periodo.date_stop),
                ('tp_reg_prev', 'in', ['1', False]),  # Somente contratos do tipo RGPS
            ]
            contratos = self.env['hr.contract'].search(domain)
            contratos_validos = []

            # Se algum contrato tiver data de término menor que a data inicial do período, tira ele
            # adiciona o trabalhador na lista de trabalhadores_com_contrato
            for contrato in contratos:
                if not contrato.date_end or contrato.date_end >= periodo.date_stop:
                    contratos_validos.append(contrato.id)

            # Se tiver algum contrato válido, cria o registro s1200
            if contratos_validos:

                # Calcula campos de mês e ano para busca dos payslip
                mes = datetime.strptime(self.periodo_id.date_start, '%Y-%m-%d').month
                ano = datetime.strptime(self.periodo_id.date_start, '%Y-%m-%d').year

                # Trabalhadores autonomos tem holerite separado
                if trabalhador.tipo != 'autonomo':
                    # Busca os payslips de pagamento mensal deste trabalhador
                    domain_payslip = [
                        ('company_id', 'in', empresas),
                        ('contract_id', 'in', contratos_validos),
                        ('mes_do_ano', '=', mes),
                        ('ano', '=', ano),
                        ('state', 'in', ['verify', 'done']),
                        ('tipo_de_folha', 'in', ['normal', 'ferias', 'decimo_terceiro']),
                    ]
                    payslips = self.env['hr.payslip'].search(domain_payslip)


                else:
                    # Busca os payslips de pagamento mensal deste autonomo
                    domain_payslip_autonomo = [
                        ('company_id', 'in', empresas),
                        ('contract_id', 'in', contratos_validos),
                        ('mes_do_ano', '=', mes),
                        ('ano', '=', ano),
                        ('state', 'in', ['verify', 'done']),
                        ('tipo_de_folha', 'in',  ['normal', 'ferias', 'decimo_terceiro']),
                    ]
                    payslips = self.env['hr.payslip.autonomo'].search(domain_payslip_autonomo)

                # Se tem payslip, cria o registro S-1200
                if payslips:

                    # Verifica se o registro S-1200 já existe, cria ou atualiza
                    domain_s1200 = [
                        ('company_id', '=', matriz.id),
                        ('trabalhador_id', '=', trabalhador.id),
                        ('periodo_id', '=', periodo.id),
                    ]
                    s1200 = self.env['sped.esocial.remuneracao'].search(domain_s1200)
                    if not s1200:
                        vals = {
                            'company_id': matriz.id,
                            'trabalhador_id': trabalhador.id,
                            'periodo_id': periodo.id,
                            'contract_ids': [(6, 0, contratos.ids)],
                        }

                        # Criar intermediario de acordo com o tipo de employee
                        if trabalhador.tipo != 'autonomo':
                            vals.update(
                                {'payslip_ids': [(6, 0, payslips.ids)]})
                        else:
                            vals.update(
                                {'payslip_autonomo_ids': [(6, 0, payslips.ids)]})

                        s1200 = self.env['sped.esocial.remuneracao'].create(vals)

                    # Se ja existe o registro apenas criar o relacionamento
                    else:
                        s1200.contract_ids = [(6, 0, contratos.ids)]

                        if trabalhador.tipo != 'autonomo':
                            s1200.payslip_ids = [(6, 0, payslips.ids)]
                        else:
                            s1200.payslip_autonomo_ids = [(6, 0, payslips.ids)]

                    # Relaciona o s1200 com o período do e-Social
                    self.remuneracao_ids = [(4, s1200.id)]

                    # Cria o registro de transmissão sped (se ainda não existir)
                    s1200.atualizar_esocial()
            else:

                # Se não tem contrato válido, remove o registro S-1200 (se existir)
                domain = [
                    ('company_id', '=', matriz.id),
                    ('trabalhador_id', '=', trabalhador.id),
                    ('periodo_id', '=', periodo.id),
                ]
                s1200 = self.env['sped.esocial.remuneracao'].search(domain)
                if s1200:
                    s1200.sped_registro.unlink()
                    s1200.unlink()

    # Controle de registros S-1202
    remuneracao_rpps_ids = fields.Many2many(
        string='Remuneração de Servidor (RPPS)',
        comodel_name='sped.esocial.remuneracao.rpps',
    )

    @api.multi
    def importar_remuneracoes_rpps(self):
        self.ensure_one()

        # Buscar Servidores
        servidores = self.env['hr.employee'].search([])

        periodo = self.periodo_id
        matriz  = self.company_id
        empresas = self.env['res.company'].search([('matriz', '=', matriz.id)]).ids
        if matriz.id not in empresas:
            empresas.append(matriz.id)

        # separa somente os trabalhadores com contrato válido neste período e nesta empresa matriz
        # servidores_com_contrato = []
        for servidor in servidores:

            # Localiza os contratos válidos deste trabalhador
            domain = [
                ('employee_id', '=', servidor.id),
                ('company_id', 'in', empresas),
                ('date_start', '<=', periodo.date_stop),
                ('tp_reg_prev', '=', '2'),  # Somente contratos do tipo RPPS
            ]
            contratos = self.env['hr.contract'].search(domain)
            contratos_validos = []

            # Se algum contrato tiver data de término menor que a data inicial do período, tira ele
            # adiciona o trabalhador na lista de trabalhadores_com_contrato
            for contrato in contratos:
                if not contrato.date_end or contrato.date_end >= periodo.date_stop:
                    contratos_validos.append(contrato.id)

            # Se tiver algum contrato válido, cria o registro s1200
            if contratos_validos:

                # Calcula campos de mês e ano para busca dos payslip
                mes = datetime.strptime(self.periodo_id.date_start, '%Y-%m-%d').month
                ano = datetime.strptime(self.periodo_id.date_start, '%Y-%m-%d').year

                # Busca os payslips de pagamento mensal deste trabalhador
                domain_payslip = [
                    ('company_id', 'in', empresas),
                    ('contract_id', 'in', contratos_validos),
                    ('mes_do_ano', '=', mes),
                    ('ano', '=', ano),
                    ('state', 'in', ['verify', 'done']),
                    ('tipo_de_folha', 'in', ['normal', 'ferias', 'decimo_terceiro']),
                ]
                payslips = self.env['hr.payslip'].search(domain_payslip)

                # Se tem payslip, cria o registro S-1202
                if payslips:

                    # Verifica se o registro S-1202 já existe, cria ou atualiza
                    domain_s1202 = [
                        ('company_id', '=', matriz.id),
                        ('servidor_id', '=', servidor.id),
                        ('periodo_id', '=', periodo.id),
                    ]
                    s1202 = self.env['sped.esocial.remuneracao.rpps'].search(domain_s1202)
                    if not s1202:
                        vals = {
                            'company_id': matriz.id,
                            'servidor_id': servidor.id,
                            'periodo_id': periodo.id,
                            'contract_ids': [(6, 0, contratos.ids)],
                            'payslip_ids': [(6, 0, payslips.ids)],
                        }
                        s1202 = self.env['sped.esocial.remuneracao.rpps'].create(vals)
                    else:
                        s1202.contract_ids = [(6, 0, contratos.ids)]
                        s1202.payslip_ids = [(6, 0, payslips.ids)]

                    # Relaciona o s1202 com o período do e-Social
                    self.remuneracao_rpps_ids = [(4, s1202.id)]

                    # Cria o registro de transmissão sped (se ainda não existir)
                    s1202.atualizar_esocial()
            else:

                # Se não tem contrato válido, remove o registro S-1202 (se existir)
                domain = [
                    ('company_id', '=', matriz.id),
                    ('servidor_id', '=', servidor.id),
                    ('periodo_id', '=', periodo.id),
                ]
                s1202 = self.env['sped.esocial.remuneracao.rpps'].search(domain)
                if s1202:
                    s1202.sped_registro.unlink()
                    s1202.unlink()

    # Controle de registros S-1210
    pagamento_ids = fields.Many2many(
        string='Pagamentos a Trabalhadores',
        comodel_name='sped.esocial.pagamento',
    )

    @api.multi
    def importar_pagamentos(self):
        self.ensure_one()

        # Buscar Servidores
        beneficiarios = self.env['hr.employee'].search([])

        periodo = self.periodo_id
        matriz  = self.company_id
        empresas = self.env['res.company'].search([('matriz', '=', matriz.id)]).ids
        if matriz.id not in empresas:
            empresas.append(matriz.id)

        # separa somente os trabalhadores com contrato válido neste período e nesta empresa matriz
        # servidores_com_contrato = []
        for beneficiario in beneficiarios:

            # Localiza os contratos válidos deste beneficiário
            domain = [
                ('employee_id', '=', beneficiario.id),
                ('company_id', 'in', empresas),
                ('date_start', '<=', periodo.date_stop),
                ('tp_reg_prev', 'in', ['1', '2']),  # Somente contratos com o campo tp_reg_prev definido como 1 ou 2
            ]
            contratos = self.env['hr.contract'].search(domain)
            contratos_validos = []

            # Se algum contrato tiver data de término menor que a data inicial do período, tira ele
            # adiciona o beneficiario na lista de beneficiarios_com_contrato
            for contrato in contratos:
                if not contrato.date_end or contrato.date_end >= periodo.date_stop:
                    contratos_validos.append(contrato.id)

            # Se tiver algum contrato válido, cria o registro s1210
            if contratos_validos:

                # Calcula campos de mês e ano para busca dos payslip
                mes = datetime.strptime(self.periodo_id.date_start, '%Y-%m-%d').month
                ano = datetime.strptime(self.periodo_id.date_start, '%Y-%m-%d').year

                # Busca os payslips de pagamento mensal deste beneficiário
                domain_payslip = [
                    ('company_id', 'in', empresas),
                    ('contract_id', 'in', contratos_validos),
                    ('mes_do_ano', '=', mes),
                    ('ano', '=', ano),
                    ('state', 'in', ['verify', 'done']),
                    ('tipo_de_folha', 'in', ['normal', 'ferias', 'decimo_terceiro', 'rescisao']),
                ]
                payslips = self.env['hr.payslip'].search(domain_payslip)

                # Se tem payslip, cria o registro S-1210
                if payslips:

                    # Verifica se o registro S-1210 já existe, cria ou atualiza
                    domain_s1210 = [
                        ('company_id', '=', matriz.id),
                        ('beneficiario_id', '=', beneficiario.id),
                        ('periodo_id', '=', periodo.id),
                    ]
                    s1210 = self.env['sped.esocial.pagamento'].search(domain_s1210)
                    if not s1210:
                        vals = {
                            'company_id': matriz.id,
                            'beneficiario_id': beneficiario.id,
                            'periodo_id': periodo.id,
                            'contract_ids': [(6, 0, contratos.ids)],
                            'payslip_ids': [(6, 0, payslips.ids)],
                        }
                        s1210 = self.env['sped.esocial.pagamento'].create(vals)
                    else:
                        s1210.contract_ids = [(6, 0, contratos.ids)]
                        s1210.payslip_ids = [(6, 0, payslips.ids)]

                    # Relaciona o s1210 com o período do e-Social
                    self.pagamento_ids = [(4, s1210.id)]

                    # Cria o registro de transmissão sped (se ainda não existir)
                    s1210.atualizar_esocial()
            else:

                # Se não tem contrato válido, remove o registro S-1210 (se existir)
                domain = [
                    ('company_id', '=', matriz.id),
                    ('beneficiario_id', '=', beneficiario.id),
                    ('periodo_id', '=', periodo.id),
                ]
                s1210 = self.env['sped.esocial.pagamento'].search(domain)
                if s1210:
                    s1210.sped_registro.unlink()
                    s1210.unlink()

    # Controle de registros S-1299
    fechamento_ids = fields.Many2many(
        string='Fechamento',
        comodel_name='sped.esocial.fechamento',
    )

    @api.multi
    def importar_fechamentos(self):
        self.ensure_one()

        # Calcula os valores do fechamento
        evt_remun = 'S' if self.remuneracao_ids or self.remuneracao_rpps_ids else 'N'
        evt_pgtos = 'S' if self.pagamento_ids else 'N'
        evt_aq_prod = 'N'
        evt_com_prod = 'N'
        evt_contrat_av_np = 'N'
        evt_infocompl_per = 'N'
        comp_sem_movto = False  # TODO Permitir que indique quando não há movimentação
        vals = {
            'company_id': self.company_id.id,
            'periodo_id': self.periodo_id.id,
            'evt_remun': evt_remun,
            'evt_pgtos': evt_pgtos,
            'evt_aq_prod': evt_aq_prod,
            'evt_com_prod': evt_com_prod,
            'evt_contrat_av_np': evt_contrat_av_np,
            'evt_infocompl_per': evt_infocompl_per,
            'comp_sem_movto': comp_sem_movto,
        }

        # Verifica se o registro S-1299 já existe, cria ou atualiza
        domain_s1299 = [
            ('company_id', '=', self.company_id.id),
            ('periodo_id', '=', self.periodo_id.id),
        ]
        s1299 = self.env['sped.esocial.fechamento'].search(domain_s1299)
        if not s1299:
            s1299 = self.env['sped.esocial.fechamento'].create(vals)
        else:
            s1299.write(vals)

        # Relaciona o s1299 com o período do e-Social
        self.fechamento_ids = [(4, s1299.id)]

        # Cria o registro de transmissão sped (se ainda não existir)
        s1299.atualizar_esocial()

    @api.multi
    def get_esocial_vigente(self, company_id=False):
        """
        Buscar o esocial vigente, se não existir um criar-lo
        :return:
        """
        if not company_id:
            raise ValidationError('Não existe o registro de uma empresa!')
        # Buscar o periodo vigente
        periodo_atual_id = self.env['account.period'].find()
        esocial_id = self.search([
            ('periodo_id', '=', periodo_atual_id.id),
            ('company_id', '=', company_id.id)
        ])

        if esocial_id:
            return esocial_id

        esocial_id = self.create(
            {
                'periodo_id': periodo_atual_id.id,
                'company_id': company_id.id,
            }
        )

        return esocial_id

    @api.depends('periodo_id', 'company_id', 'nome')
    def _compute_readonly(self):
        for esocial in self:
            esocial.nome_readonly = esocial.nome
            esocial.periodo_id_readonly = esocial.periodo_id
            esocial.company_id_readonly = esocial.company_id

    @api.depends('periodo_id', 'company_id')
    def _compute_nome(self):
        for esocial in self:
            nome = esocial.periodo_id.name
            if esocial.company_id:
                nome += '-' + esocial.company_id.name
            if esocial.periodo_id:
                nome += ' (' + esocial.periodo_id.name + ')'
            esocial.nome = nome
