# -*- coding: utf-8 -*-
# Copyright 2018 ABGF
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import api, fields, models
from openerp.exceptions import Warning


class AccountEventTemplate(models.Model):
    _name = 'account.event.template'

    name = fields.Char(
        string='Nome',
    )

    lote_lancamento_id = fields.Many2one(
        string=u'Lote de Lançamentos',
        comodel_name='account.journal',
    )

    account_formula = fields.Selection(
        string=u'Fórmula',
        selection=[
            (1, '1ª Fórmula'),
            (2, '2ª Fórmula'),
            (3, '3ª Fórmula'),
            (4, '4ª Fórmula'),
        ],
    )

    account_event_template_line_ids = fields.One2many(
        string='Partidas',
        comodel_name='account.event.template.line',
        inverse_name='account_event_template_id',
    )

    def validar_primeira_formula(self):
        if self.account_formula == 1:
            for partida in self.account_event_template_line_ids:
                if not partida.account_debito_id or not partida.account_credito_id:
                    raise Warning(
                        'Nos lançamentos de 1ª Fórmula é '
                        'necessário que todas as partidas possuam uma '
                        'conta de débito e uma de crédito!'
                    )

    def validar_segunda_terceira_formula(self):
        if self.account_formula in (2, 3):
            if self.account_formula == 2:
                tipo_conta = 'debito'
            else:
                tipo_conta = 'credito'
            contador = 0
            for partida in self.account_event_template_line_ids:
                if partida.account_debito_id and partida.account_credito_id:
                    raise Warning(
                        'Em 2ª e 3ª fórmula as partidas só '
                        'podem ter uma conta associada!'
                    )
                if tipo_conta == 'debito' and partida.account_debito_id:
                    contador += 1
                elif tipo_conta == 'credito' and partida.account_credito_id:
                    contador += 1

            if contador > 1:
                raise Warning(
                    'Nesta fórmula de lançamento só é '
                    'permitido uma conta do tipo {}!'.format(tipo_conta)
                )
            elif not contador:
                raise Warning(
                    'Nesta fórmula de lançamento é preciso '
                    'inserir uma conta do tipo {}'.format(tipo_conta)
                )

    def validar_formula_roteiro_contabil(self):
        self.validar_primeira_formula()
        self.validar_segunda_terceira_formula()

    # @api.model
    # def create(self, vals):
    #     res = super(AccountEventTemplate, self).create(vals)
    #
    #     res.validar_formula_roteiro_contabil()
    #
    #     return res
    #
    # @api.multi
    # def write(self, vals):
    #     res = super(AccountEventTemplate, self).create(vals)
    #
    #     self.validar_formula_roteiro_contabil()

        # return res

    def validar_dados(self, dados):
        """
        validar o dict para criacao de lenaçamentos

        Exemplo:
        {
            'data':         '2019-01-01',
            'lines':        [{'LIQUIDO': 100.00}, {'INSS': 123.45}]
            'ref':          identificação do módulo de origem

            'model':        (opcional) model de origem
            'res_id':       (opcional) id do registro de origem
            'period_id'        (opcional) account.period
            'company_id':   (opcional) res.company
        }

        """
        return True

    def preparar_dados_lancamentos(self, dados):
        """
        {
            'data':         '2019-01-01',
            'lines':        [{'code': 'LIQUIDO', 'valor': 123},
                             {'code': 'INSS', 'valor': 621.03}],
            'ref':          identificação do módulo de origem
            'model':        (opcional) model de origem
            'res_id':       (opcional) id do registro de origem
            'period_id'     (opcional) account.period
            'company_id':   (opcional) res.company
        }
        """

        account_move_ids = []

        for line in dados.get('lines'):

            account_template_line_id = self.get_linha_roteiro(line.get('code'))


            account_move_debit_line = {
                'account_id': account_template_line_id.account_debito_id.id,
                'debit': line.get('valor'),
                'credit': 0.0,
                'name': 'NAME',
            }

            account_move_credit_line = {
                'account_id': account_template_line_id.account_credito_id.id,
                'credit': line.get('valor'),
                'debit': 0.0,
                'name': 'NAME',
            }

            historico_padrao_id = \
                account_template_line_id.historico_padrao_id.get_historico_padrao()

            account_move_id = {
                'ref': dados.get('ref'),
                'narration': historico_padrao_id,
                'resumo': historico_padrao_id,
                'date': dados.get('data'),
                'line_id':
                    [(0, 0, account_move_debit_line),
                     (0,0, account_move_credit_line)]
            }

            account_move_ids.append(account_move_id)

        return account_move_ids


    def criar_lancamentos(self, vals):
        """
        :param vals:
        :return:
        """
        account_move_obj = self.env['account.move']
        for lancamento in vals:
            account_move_obj.create(lancamento)


    def get_linha_roteiro(self, code):
        """
        retornar a linha do roteiro contabil

        """
        return self.account_event_template_line_ids.\
            filtered(lambda x: x.code == code)


    def gerar_contabilizacao(self, dados):
        """
        Rotina principal:
        """

        self.validar_dados(dados)

        account_move_ids = self.preparar_dados_lancamentos(dados)

        self.criar_lancamentos(account_move_ids)

        return True
