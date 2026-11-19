# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, models
from odoo.exceptions import UserError

# Context key that hands the inbox document to the import that the window of the
# access key runs, which reaches ``_edi_import_files`` through the window
DFE_DOCUMENT_CONTEXT_KEY = "edi_import_dfe_document_id"


class Document(models.Model):
    _inherit = "l10n_br_fiscal.document"

    @api.model
    def _edi_import_files(self, files, dfe_document=None):
        if not dfe_document and self.env.context.get(DFE_DOCUMENT_CONTEXT_KEY):
            dfe_document = self.env["l10n_br_fiscal_dfe.document"].browse(
                self.env.context[DFE_DOCUMENT_CONTEXT_KEY]
            )
        return super()._edi_import_files(files, dfe_document=dfe_document)

    @api.model
    def _edi_import_file(self, name, content, dfe_document=None):
        document, created = super()._edi_import_file(
            name, content, dfe_document=dfe_document
        )
        if created and dfe_document:
            document.message_post(
                body=_("Document created from the access key %s.")
                % dfe_document.access_key
            )
            dfe_document.sudo().message_post(
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
