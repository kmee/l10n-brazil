# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class FiscalDocumentLineMixin(models.AbstractModel):
    _inherit = "l10n_br_fiscal.document.line.mixin"

    def _is_imported(self):
        if super()._is_imported():
            return True
        document = getattr(self, "document_id", None)
        return bool(document and document.mirror_document)
