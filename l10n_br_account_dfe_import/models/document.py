# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import UserError


class Document(models.Model):
    _inherit = "l10n_br_fiscal.document"

    def action_generate_invoice(self):
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
        unconfirmed = self.fiscal_line_ids.filtered(
            lambda line: line.partner_uom_code
            and not line.import_uom_id
            and self.env["uom.uom"]._match_by_fiscal_code(line.partner_uom_code)
            != line.uom_id
        )
        if unconfirmed:
            raise UserError(
                _(
                    "Choose the unit of the lines before generating the invoice, "
                    "the unit declared by the supplier has no match:\n%s"
                )
                % "\n".join(
                    f"- {line.name} ({line.partner_uom_code})" for line in unconfirmed
                )
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
