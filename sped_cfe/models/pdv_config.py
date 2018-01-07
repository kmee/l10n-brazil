# -*- coding: utf-8 -*-
#
# Copyright 2017 KMEE INFORMATICA LTDA
#   Luis Felipe Miléo <mileo@kmee.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from __future__ import division, print_function, unicode_literals

import os
import logging

from odoo import api, fields, models
from odoo.addons.l10n_br_base.constante_tributaria import *
from odoo.exceptions import UserError, Warning


_logger = logging.getLogger(__name__)

try:
    from pybrasil.inscricao import limpa_formatacao
    from pybrasil.data import (parse_datetime, UTC, data_hora_horario_brasilia,
                               agora)
    from pybrasil.valor import formata_valor
    from pybrasil.valor.decimal import Decimal as D
    from pybrasil.template import TemplateBrasil

    from satcomum.ersat import ChaveCFeSAT
    from satcfe.entidades import *
    from satcfe.excecoes import ExcecaoRespostaSAT, ErroRespostaSATInvalida

except (ImportError, IOError) as err:
    _logger.debug(err)


class ConfiguracaoPDV(models.Model):
    _name = b'pdv.config'

    name = fields.Char(
        String=u"Nome do PDV",
        required=True
    )

    vendedor = fields.Many2one(
        comodel_name='res.users',
        string=u'Vendedor',
    )

    numero_caixa = fields.Char(string=u'Número de caixa')

    tipo = fields.Selection([('SAT', 'SAT'),
                             ], string=u'Tipo')

    impressora = fields.Many2one(
        'impressora.config',
        'Impressora',
    )

    tipo_sat = fields.Selection([
        ('local', 'Local'),
        ('rede_interna', 'Rede Interna'),
        ('remoto', 'Remoto'),
    ], string=u'Tipo SAT')

    path_integrador = fields.Char(
        string=u'Caminho do Integrador'
    )

    ip = fields.Char(string=u'IP')

    porta = fields.Char(
        string=u'Porta'
    )

    ambiente = fields.Selection([
        ('producao', 'Produção'),
        ('homologacao', 'Homologação'),
    ], string=u'Ambiente')

    codigo_ativacao = fields.Char(string=u'Código de Ativação')

    cnpjsh = fields.Char(string=u'CNPJ Homologação')

    ie = fields.Char(string=u'Inscrição Estadual Homologação')

    chave_ativacao = fields.Char(string=u'Chave de Ativação')

    cnpj_software_house = fields.Char(
        string=u"CNPJ Software House"
    )

    assinatura = fields.Char(
        string=u"Assinatura"
    )

    site_consulta_qrcode = fields.Char(
        string=u"Site Sefaz"
    )

    chave_acesso_validador = fields.Char(
        string=u'Chave Acesso Validador',
    )
    chave_requisicao = fields.Char(string=u'Chave de Requisição')
    estabelecimento = fields.Char(string=u'Estabelecimento')
    serial_pos = fields.Char(string=u'Serial POS')
    id_fila_validador = fields.Char(string=u'ID Fila Validador')
    multiplos_pag = fields.Boolean(string=u'Habilitar Múltiplos Pagamentos')
    anti_fraude = fields.Boolean(string=u'Habilitar Anti-Fraude')

    def processador_cfe(self):
        """
        Busca classe do processador do cadastro da empresa, onde podemos ter três tipos de processamento dependendo
        de onde o equipamento esta instalado:

        - Instalado no mesmo servidor que o Odoo;
        - Instalado na mesma rede local do servidor do Odoo;
        - Instalado em um local remoto onde o browser vai ser responsável por se comunicar com o equipamento

        :return:
        """
        self.ensure_one()

        if self.tipo_sat == 'local':
            from mfecfe.clientelocal import ClienteSATLocal
            from mfecfe import BibliotecaSAT
            cliente = ClienteSATLocal(
                BibliotecaSAT(self.path_integrador),
                codigo_ativacao=self.codigo_ativacao
            )
        elif self.tipo_sat == 'rede_interna':
            from mfecfe.clientesathub import ClienteSATHub
            cliente = ClienteSATHub(
                self.ip,
                self.porta,
                numero_caixa=int(self.numero_caixa)
            )
        elif self.tipo_sat == 'remoto':
            cliente = None
            # NotImplementedError

        if not self.impressora:
            return cliente, None
        elif not self.impressora.ip:
            return cliente, cliente
        elif self.impressora.ip:
            impressora = ClienteSATHub(
                self.impressora.ip,
                self.impressora.porta,
                numero_caixa=int(self.numero_caixa)
            )
            return cliente, impressora
        raise UserError("Falha na configuração do Caixa")
