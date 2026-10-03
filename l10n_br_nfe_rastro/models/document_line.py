# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class FiscalDocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    def _nfe40_rastro_is_required(self):
        """Whether the NF-e must carry the traceability group for this line.

        The layout only makes it mandatory for medicines (rule K01-20),
        so nothing is required here; modules adding product specific
        groups extend this method.
        """
        self.ensure_one()
        return False
