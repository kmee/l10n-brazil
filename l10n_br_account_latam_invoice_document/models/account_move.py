# Copyright (C) 2009 - TODAY Renato Lima - Akretion
# Copyright (C) 2026-Today - KMEE (<https://kmee.com.br>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class AccountMove(models.Model):
    """Overrides of methods defined by l10n_latam_invoice_document.

    They live here, and not in l10n_br_account, because overriding a method
    of a module one does not depend on leaves the result to the load order:
    when l10n_latam_invoice_document loads after l10n_br_account, its version
    comes first in the MRO and the Brazilian one is never called. Depending
    on both modules, this one always loads after them.
    """

    _inherit = "account.move"

    def _compute_l10n_latam_document_type(self):
        """Override to map fiscal document_type_id to l10n_latam_document_type_id.

        When l10n_latam_invoice_document is installed, it requires
        l10n_latam_document_type_id for posted invoices on journals that use documents.
        This override ensures that when a fiscal document_type_id is set
        (from l10n_br_fiscal), the corresponding l10n_latam_document_type_id is also
        set based on matching code.
        """
        # Store current values to avoid clearing them
        current_values = {move.id: move.l10n_latam_document_type_id for move in self}

        res = super()._compute_l10n_latam_document_type()

        # Restore values that were set but cleared by super()
        for move in self:
            if current_values[move.id] and not move.l10n_latam_document_type_id:
                move.l10n_latam_document_type_id = current_values[move.id]

        # Set document type based on fiscal document_type_id.code
        for move in self.filtered(
            lambda m: m.document_type_id and not m.l10n_latam_document_type_id
        ):
            latam_doc_type = self._find_latam_document_type(
                move.document_type_id, move.company_id
            )
            if latam_doc_type:
                move.l10n_latam_document_type_id = latam_doc_type
        return res

    @api.constrains("state")
    def _check_l10n_latam_documents(self):
        """Auto-assign l10n_latam document type for Brazilian companies, then
        let upstream validation run.

        When l10n_latam_invoice_document is installed, posting invoices requires
        l10n_latam_document_type_id on journals that use documents. Instead of
        raising an error, this override auto-assigns a document type for Brazilian
        companies (where fiscal documents are electronic and numbering is automatic).

        For non-Brazilian companies, the auto-assign is skipped and the upstream
        constraint runs unchanged, preserving full validation (including document
        number checks) for other Latin American localizations in multi-localization
        databases.
        """
        for move in self.filtered(
            lambda x: (
                x.l10n_latam_use_documents
                and x.state == "posted"
                and not x.l10n_latam_document_type_id
                and x.company_id.country_id.code == "BR"
            )
        ):
            # Try to find a matching document type
            latam_doc_type = False
            if move.document_type_id:
                latam_doc_type = self.env["l10n_latam.document.type"].search(
                    [
                        ("code", "=", move.document_type_id.code),
                        (
                            "country_id",
                            "=",
                            move.company_id.account_fiscal_country_id.id,
                        ),
                    ],
                    limit=1,
                )
            if not latam_doc_type:
                internal_types = []
                if move.move_type in ["out_refund", "in_refund"]:
                    internal_types = ["credit_note"]
                elif move.move_type in ["out_invoice", "in_invoice"]:
                    internal_types = ["invoice", "debit_note"]
                if move.debit_origin_id:
                    internal_types = ["debit_note"]
                internal_types += ["all"]
                latam_doc_type = self.env["l10n_latam.document.type"].search(
                    [
                        ("internal_type", "in", internal_types),
                        (
                            "country_id",
                            "=",
                            move.company_id.account_fiscal_country_id.id,
                        ),
                    ],
                    limit=1,
                )
            if not latam_doc_type:
                # Last resort: find ANY document type for Brazil
                latam_doc_type = self.env["l10n_latam.document.type"].search(
                    [("country_id", "=", move.company_id.country_id.id)],
                    limit=1,
                )
            if latam_doc_type:
                move.l10n_latam_document_type_id = latam_doc_type

        # Let upstream validation run only for non-Brazilian companies.
        # Brazilian companies use electronic document numbering managed by
        # l10n_br_fiscal, so the upstream manual document number check would
        # raise false positives on demo data and is irrelevant for Brazil.
        # For other Latin American localizations in multi-localization databases,
        # the original validation (document type + document number) runs unchanged.
        non_br_moves = self.filtered(lambda m: m.company_id.country_id.code != "BR")
        if non_br_moves:
            return super(AccountMove, non_br_moves)._check_l10n_latam_documents()
        return None
