# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, models
from odoo.exceptions import UserError


class Document(models.Model):
    _inherit = "l10n_br_fiscal.document"

    @api.model
    def _edi_import_file(self, name, content, dfe_document=None):
        document, created = super()._edi_import_file(
            name, content, dfe_document=dfe_document
        )
        if created and dfe_document:
            # A note in the history, sent to nobody: message_post needs the email of
            # the sender, which a fiscal user may not have
            document._message_log(
                body=_("Document created from the access key %s.")
                % dfe_document.access_key
            )
            dfe_document.sudo()._message_log(
                body=_("Fiscal document %s created.") % document.display_name
            )
        return document, created

    @api.model
    def _edi_import_check(self, parsed, company):
        """The state the inbox knows about the note: cancelled or denied in the
        source (the criterion of OCA/l10n-brazil#5589 by Marcel Savegnago)."""
        dfe_document = (
            self.env["l10n_br_fiscal_dfe.document"]
            .sudo()
            .search(
                [
                    ("access_key", "=", parsed.access_key),
                    ("company_id", "=", company.id),
                ],
                limit=1,
            )
        )
        reason = dfe_document and dfe_document._dfe_import_block_reason()
        if reason:
            raise UserError(reason)
        return super()._edi_import_check(parsed, company)
