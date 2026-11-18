# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class DocumentImportWizard(models.TransientModel):
    _inherit = "l10n_br_fiscal.document.import.wizard"

    def _import_block_reason(self):
        reason = super()._import_block_reason()
        if reason:
            return reason
        # a file whose note the DF-e inbox knows as cancelled or denied
        return self.env["l10n_br_fiscal_dfe.document"]._import_block_reason_for_key(
            self.document_key
        )
