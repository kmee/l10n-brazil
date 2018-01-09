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


class ConfiguracaoImpressora(models.Model):
    _name = b'impressora.config'
    _rec_name = 'nome'

    nome = fields.Char(string=u'Nome')
    pdv_config_ids = fields.Many2one(
        comodel_name='pdv.config',
        string='Impressora',
    )
    ip = fields.Char(
        string=u'IP',
        help=u"""Deixar em branco para usar o do caixa"""
    )
    porta = fields.Char(
        string=u'Porta',
        help=u"""Deixar em branco para usar o do caixa"""
    )
    modelo = fields.Selection([
        ('bematech', 'Bematech MP-4200 TH'),
        ('daruma', 'Daruma DR700'),
        ('elgini9', 'Elgin I9'),
        ('elgini7', 'Elgin I7'),
        ('epson', 'Epson TM-T20'),
    ], string=u'Modelo')
    forma = fields.Selection([
        ('usb', 'USB'),
        ('file', 'File'),
        ('rede', 'Rede'),
        ('serial', 'Serial'),
        ('dummy', 'Dummy')
    ], string=u'Forma de Impressão')
    conexao = fields.Char(string=u'Conexão')

