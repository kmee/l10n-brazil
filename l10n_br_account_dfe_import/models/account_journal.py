# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, models


class AccountJournal(models.Model):
    _inherit = "account.journal"

    def create_document_from_attachment(self, attachment_ids=None):
        if self.env.company.country_id.code != "BR" or not attachment_ids:
            return super().create_document_from_attachment(
                attachment_ids=attachment_ids
            )
        wizard = self.env["l10n_br_fiscal_dfe_import.wizard"].create(
            {"attachment_ids": [Command.set(attachment_ids)]}
        )
        return wizard.action_import()
