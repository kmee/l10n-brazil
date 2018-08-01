# -*- coding: utf-8 -*-
# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

from openerp.addons.l10n_br_account_product.constantes import (
    FORMA_PAGAMENTO,
    BANDEIRA_CARTAO,
    INTEGRACAO_CARTAO,
    INTEGRACAO_CARTAO_NAO_INTEGRADO,
    FORMA_PAGAMENTO_CARTOES,
    FORMA_PAGAMENTO_CARTAO_CREDITO,
    FORMA_PAGAMENTO_CARTAO_DEBITO,
    FORMA_PAGAMENTO_OUTROS,
    FORMA_PAGAMENTO_DICT,
    BANDEIRA_CARTAO_DICT,
)

from openerp import api, fields, models


class AccountPaymentTerm(models.Model):
    _inherit = b'account.payment.term'
    _rec_name = 'nome_comercial'

    sped_forma_pagamento_id = fields.Many2one(
        string='Forma de pagamento',
        comodel_name='sped.forma.pagamento',
    )
    nome_comercial = fields.Char(
        string='Condição da pagamento',
        compute='_compute_nome_comercial',
    )

    @api.multi
    def _compute_nome_comercial(self):
        for payment_term in self:
            nome_comercial = ''
            forma_pagamento = \
                payment_term.sped_forma_pagamento_id.forma_pagamento
            if forma_pagamento in FORMA_PAGAMENTO_CARTOES:
                if forma_pagamento == \
                        FORMA_PAGAMENTO_CARTAO_CREDITO:
                    nome_comercial += '[Crédito '
                elif forma_pagamento == \
                        FORMA_PAGAMENTO_CARTAO_DEBITO:
                    nome_comercial += '[Débito '

                nome_comercial += \
                    BANDEIRA_CARTAO_DICT[payment_term.bandeira_cartao]
                nome_comercial += '] '
            elif forma_pagamento == FORMA_PAGAMENTO_OUTROS:
                nome_comercial += '['
                nome_comercial += payment_term.sped_forma_pagamento_id.name
                nome_comercial += '] '
            elif forma_pagamento:
                nome_comercial += '['
                nome_comercial += \
                    FORMA_PAGAMENTO_DICT[forma_pagamento]
                nome_comercial += '] '

            nome_comercial += payment_term.name

            payment_term.nome_comercial = nome_comercial
