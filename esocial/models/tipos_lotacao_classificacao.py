# -*- coding: utf-8 -*-
#
# Copyright 2017 KMEE
#   Wagner Pereira <wagner.pereira@kmee.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from odoo import fields, models


class TipoLotacaoClassificacao(models.Model):
    _name = "esocial.lotacao_classificacao"
    _description = 'Compatibilidade entre Tipos de Lotação' \
                   ' e Classificação Tributária'

    name = fields.Char(string='Class. Tributária')
    classificacao_tributaria_ids = fields.Many2many(
        'esocial.lotacao_tributaria', string='Tipos de Lotação Tributária',
        relation='classificacao_tributaria_codigo_ids'
    )
