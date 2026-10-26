# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    # O campo herdado por delegação de l10n_br_fiscal.document nasce com
    # comodel "mdfe.30.autxml", que é modelo ABSTRATO, enquanto no próprio
    # documento fiscal o campo é res.partner, que é o correto. Qualquer valor
    # não vazio derruba a criação da fatura:
    #
    #   AttributeError: 'mdfe.30.autxml' object has no attribute 'id'
    #   odoo/fields.py, convert_to_cache -> browse(it).id
    #
    # Vem da ordem em que o spec_driven_model concretiza o comodel: o campo
    # delegado é copiado antes de "mdfe.30.autxml" virar res.partner. O
    # nfe40_autXML tem exatamente o mesmo defeito e não aparece só porque o
    # default dele devolve lista vazia, então nada chega a ser convertido.
    #
    # Redeclarado aqui com o comodel concreto.
    mdfe30_autXML = fields.One2many(
        comodel_name="res.partner",
        related="fiscal_document_id.mdfe30_autXML",
        readonly=False,
    )


class AccountBankStatementLine(models.Model):
    _inherit = "account.bank.statement.line"

    # Mesma correção: a linha de extrato delega para account.move, então criar
    # uma também cria o movimento e passa pelo mesmo campo.
    mdfe30_autXML = fields.One2many(
        comodel_name="res.partner",
        related="move_id.mdfe30_autXML",
        readonly=False,
    )
