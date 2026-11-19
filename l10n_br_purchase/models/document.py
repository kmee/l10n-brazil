# Copyright 2026 KMEE - Luis Felipe Mileo <mileo@kmee.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models


class FiscalDocument(models.Model):
    _inherit = "l10n_br_fiscal.document"

    has_suggested_import_origin = fields.Boolean(
        compute="_compute_has_suggested_import_origin",
        help="Technical: some line of the imported document has an origin "
        "suggestion waiting for confirmation.",
    )

    @api.depends("imported_document", "fiscal_line_ids.import_origin_state")
    def _compute_has_suggested_import_origin(self):
        for document in self:
            document.has_suggested_import_origin = bool(
                document.imported_document
                and "suggested"
                in document.fiscal_line_ids.mapped("import_origin_state")
            )

    def _init_import_states(self):
        result = super()._init_import_states()
        for document in self.filtered("imported_document"):
            document.fiscal_line_ids._suggest_import_origin()
        return result

    def action_confirm_import_origins(self):
        """Confirm, in one step, the origins suggested on the lines."""
        for document in self:
            document.fiscal_line_ids.filtered(
                lambda line: line.import_origin_state == "suggested"
            ).write({"import_origin_state": "resolved"})
        return True

    def _import_review_errors(self):
        errors = super()._import_review_errors()
        if not self.imported_document:
            return errors
        # a pending origin only waits for a decision when there is an order
        # line to choose: with none open for the product there is nothing to
        # decide, and the bill simply has no order
        unconfirmed = self.fiscal_line_ids.filtered(
            lambda line: (
                line.import_origin_state == "suggested"
                or (
                    line.import_origin_state == "pending"
                    and line.import_origin_candidate_ids
                )
            )
        )
        if unconfirmed:
            errors.append(
                _(
                    "- %(count)s line(s) with the origin (purchase order line) "
                    "not decided yet: use Confirm Origins to accept the "
                    "suggestions, choose the order line of each one, or mark "
                    "the origin of the line as Resolved to go on without an order.",
                    count=len(unconfirmed),
                )
            )
        return errors
