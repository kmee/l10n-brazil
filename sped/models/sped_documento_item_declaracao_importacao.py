# -*- coding: utf-8 -*-
#
# Copyright 2016 Taŭga Tecnologia
#   Aristides Caldeira <aristides.caldeira@tauga.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from odoo import fields, models
from odoo.addons.l10n_br_base.models.sped_base import SpedBase
from odoo.addons.l10n_br_base.constante_tributaria import (
    INTERMEDIACAO_IMPORTACAO,
    VIA_TRANSPORTE_IMPORTACAO,
)


class SpedDocumentoItemDeclaracaoImportacao(SpedBase, models.Model):
    _name = 'sped.documento.item.declaracao.importacao'
    _description = 'Declarações de Importação do Item do Documento Fiscal'

    item_id = fields.Many2one(
        comodel_name='sped.documento.item',
        string='Item do Documento',
        ondelete='cascade',
        required=True,
    )
    numero_documento = fields.Char(
        string='Nº do documento de importação',
        size=12,
    )
    data_registro = fields.Date(
        string='Data de registro',
    )
    local_desembaraco = fields.Char(
        string='Local do desembaraço',
        size=60,
    )
    uf_desembaraco_id = fields.Many2one(
        comodel_name='sped.estado',
        string='Estado do desembaraço',
    )
    data_desembaraco = fields.Date(
        string='Data do desembaraço',
    )
    via_trans_internacional = fields.Selection(
        selection=VIA_TRANSPORTE_IMPORTACAO,
        string='Via de transporte internacional',
    )
    vr_afrmm = fields.Monetary(
        string='Valor do AFRMM',
    )
    forma_importacao = fields.Selection(
        selection=INTERMEDIACAO_IMPORTACAO,
        string='Forma de importação',
    )
    participante_id = fields.Many2one(
        comodel_name='sped.participante',
        string='Adquirente/encomendante',
    )

    #
    # Quando houver uma única adição, o que é o mais comum,
    # preencher diretamente no registro da DI
    #
    numero_adicao = fields.Integer(
        string='Nº da adição',
        default=1,
    )
    sequencial = fields.Integer(
        string='Sequencial',
        default=1,
    )
    vr_desconto = fields.Monetary(
        string='Valor do desconto',
    )
    numero_drawback = fields.Integer(
        string='Nº drawback',
    )


class DocumentoItem(models.Model):
    _inherit = 'sped.documento.item'

    declaracao_ids = fields.One2many(
        comodel_name='sped.documento.item.declaracao.importacao',
        inverse_name='item_id',
        string='Declarações de importação',
    )
