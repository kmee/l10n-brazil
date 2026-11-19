# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class DocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    @api.depends("product_id", "proxy_name")
    def _compute_name(self):
        # l10n_br_account replaces the fiscal compute, which keeps the
        # description declared in an imported file
        imported = self.filtered(lambda line: line._is_imported() and line.name)
        return super(DocumentLine, self - imported)._compute_name()
