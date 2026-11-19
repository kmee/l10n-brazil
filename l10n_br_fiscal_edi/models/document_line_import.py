# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models

from odoo.addons.l10n_br_fiscal.constants.fiscal import FISCAL_OUT


class DocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    def _find_or_create_supplierinfo(self):
        """The partner of a document the company issued is a customer: what the
        review of its lines teaches is not a mapping of a supplier."""
        received = self.filtered(
            lambda line: line.document_id.fiscal_operation_type != FISCAL_OUT
        )
        return super(DocumentLine, received)._find_or_create_supplierinfo()
