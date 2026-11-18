# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class FiscalDocument(models.Model):
    _inherit = "l10n_br_fiscal.document"

    def _import_block_reason(self):
        reason = super()._import_block_reason()
        if reason or not self.document_key:
            return reason
        # cancelled or denied at the source, as the DF-e inbox knows
        return self.env["l10n_br_fiscal_dfe.document"]._import_block_reason_for_key(
            self.document_key
        )
