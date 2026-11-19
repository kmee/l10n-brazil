# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    DOCUMENT_ISSUER_COMPANY,
    DOCUMENT_STATE_DRAFT,
)


class Document(models.Model):
    _inherit = "l10n_br_fiscal.document"

    def action_generate_invoice(self):
        """Create the vendor bill of an imported document. The payables are born
        with it, not with the import."""
        self.ensure_one()
        if not self.env["account.move"].check_access_rights(
            "create", raise_exception=False
        ):
            raise UserError(
                _(
                    "Generating the invoice needs the accounting rights of the "
                    "Billing group. Ask a user that has them."
                )
            )
        pending = self.fiscal_line_ids.filtered(
            lambda line: line.import_state != "resolved"
        )
        if pending:
            raise UserError(
                _("Resolve the lines before generating the invoice:\n%s")
                % "\n".join(f"- {line.name}" for line in pending)
            )
        self._check_document_import()
        move_form = self.env["account.move"].import_fiscal_document(
            self, move_type=f"{self.fiscal_operation_type}_invoice"
        )
        return {
            "name": _("Invoice"),
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": move_form.id,
            "views": [(False, "form")],
            "view_mode": "form",
            "target": "current",
        }

    def _edi_draft_move(self):
        """The draft invoice that will issue this document, if there is one."""
        self.ensure_one()
        if (
            self.issuer == DOCUMENT_ISSUER_COMPANY
            and self.state_edoc == DOCUMENT_STATE_DRAFT
        ):
            return self.move_ids[:1]
        return self.env["account.move"]

    def _edi_display_installments(self):
        move = self._edi_draft_move()
        return move._edi_installments() if move else super()._edi_display_installments()

    def _edi_display_payments(self):
        move = self._edi_draft_move()
        return move._edi_payments() if move else super()._edi_display_payments()
