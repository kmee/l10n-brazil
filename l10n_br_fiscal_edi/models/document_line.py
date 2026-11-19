# Copyright (C) 2026  Raphaël Valyi - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import models


class FiscalDocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    def _apply_import_match_source(self, source, trusted=False):
        """Hook: record on the persisted line the match source (origin) the
        operator picked in the import wizard. The modules that know the
        origin models (purchase, stock) extend it.

        ``trusted`` says the origin needs no further review: the operator chose
        it in the grid, or the supplier declared it in the file."""
        self.ensure_one()
