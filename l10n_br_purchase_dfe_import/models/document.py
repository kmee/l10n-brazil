# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval


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

    def _dfe_import_suggest_operation(self, inf_nfe):
        result = super()._dfe_import_suggest_operation(inf_nfe)
        # the operation comes after the origins were decided: the destination
        # of the order is applied now
        self.fiscal_line_ids.filtered(
            lambda line: line.import_origin_state == "resolved"
        )._apply_import_origin_operation_line()
        return result

    def action_confirm_import_origins(self):
        """Confirm, in one step, the origins suggested on the lines."""
        for document in self:
            document.fiscal_line_ids.filtered(
                lambda line: line.import_origin_state == "suggested"
            ).write({"import_origin_state": "resolved"})
        return True

    def _import_undecided_origin_lines(self):
        """Lines whose origin waits for a person: a suggestion, or a pending
        choice with an order line to choose from."""
        self.ensure_one()
        return self.fiscal_line_ids.filtered(
            lambda line: line.import_origin_state == "suggested"
            or (
                line.import_origin_state == "pending"
                and line.import_origin_candidate_ids
            )
        )

    def action_generate_invoice(self):
        self.ensure_one()
        undecided = self._import_undecided_origin_lines()
        if undecided:
            raise UserError(
                _(
                    "%(count)s line(s) have the origin (purchase order line) "
                    "not decided yet. Use Confirm Origins to accept the "
                    "suggestions, or Match with Orders to choose the order line "
                    "of each one or to mark the line as without order.",
                    count=len(undecided),
                )
            )
        return super().action_generate_invoice()

    def action_open_origin_match(self):
        """Open the reconciliation of the document with orders and quotations
        of its supplier."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "l10n_br_purchase_dfe_import.document_match_action"
        )
        domain = [
            ("company_id", "=", self.company_id.id),
            ("partner_id", "=", self.partner_id.commercial_partner_id.id),
            "|",
            ("fiscal_document_id", "=", self.id),
            ("kind", "!=", "note"),
        ]
        lines = self.fiscal_line_ids
        products = lines.product_id
        if lines and all(line.product_id for line in lines):
            # every product is known: only the lines that can be the origin
            domain.append(("product_id", "in", products.ids))
        action["domain"] = domain
        action["context"] = dict(
            safe_eval(action["context"]), match_document_id=self.id
        )
        action["name"] = _("Match with Orders: %s", self.display_name)
        return action
