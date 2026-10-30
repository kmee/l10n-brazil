# Copyright (C) 2026 - TODAY, KMEE (<https://kmee.com.br>)
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, models

from odoo.addons.l10n_br_fiscal.constants.fiscal import DOCUMENT_ISSUER_COMPANY


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.depends(
        "l10n_latam_document_type_id",
        "journal_id",
        "issuer",
        "document_type_id",
        "fiscal_document_id",
    )
    def _compute_l10n_latam_manual_document_number(self):
        # Soft dependency: only called when l10n_latam_invoice_document is
        # installed, which defines the field and this compute.
        return super()._compute_l10n_latam_manual_document_number()

    def _is_manual_document_number(self):
        """A fiscal document issued by the company is numbered by its serie,
        also when it is booked in a purchase journal, which is the case of the
        inbound NF-e of an import: there is no vendor number to type in.

        The same override exists in l10n_br_account, where it never takes
        effect: l10n_latam_invoice_document is a soft dependency, it is loaded
        after l10n_br_account (same depth, later name) and its own definition
        wins the MRO. Here it does take effect, because this module is deeper
        in the dependency graph than l10n_latam_invoice_document.
        """
        if self.document_type_id and self.issuer == DOCUMENT_ISSUER_COMPANY:
            return False
        return super()._is_manual_document_number()
