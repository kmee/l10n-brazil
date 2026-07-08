# Copyright 2019 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models

from odoo.addons.account.models.account_move import AccountMove as CoreAccountMove


class AccountMove(models.Model):
    _inherit = "account.move"

    def button_draft(self):
        if self.env.context.get("paulistana_cancelling"):
            # Estamos dentro do _document_cancel de um NFS-e Paulistana:
            # cancel_move_ids -> move.button_cancel -> (fatura posted) ->
            # button_draft. O l10n_br_account.button_draft levantaria
            # "cancelled in SEFAZ" (state_edoc == CANCELADA + issuer == COMPANY,
            # situação criada pelo próprio _change_state alguns frames acima)
            # e/ou resetaria state_edoc para EM_DIGITACAO via
            # action_document_back2draft — nenhuma das duas coisas queremos
            # aqui: já estamos cancelando de propósito. Chamamos direto o
            # button_draft do Odoo core, pulando o override do l10n_br_account.
            return CoreAccountMove.button_draft(self)
        return super().button_draft()
