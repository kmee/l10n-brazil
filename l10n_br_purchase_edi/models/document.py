# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    DOCUMENT_ISSUER_PARTNER,
    DOCUMENT_STATE_CANCEL,
    SITUACAO_EDOC_DENEGADA,
    SITUACAO_EDOC_INUTILIZADA,
)

# the document of a supplier is authorized when it arrives: what is still open
# is the bill, so a document is open until its bill is posted
CLOSED_DOCUMENT_STATES = (
    DOCUMENT_STATE_CANCEL,
    SITUACAO_EDOC_DENEGADA,
    SITUACAO_EDOC_INUTILIZADA,
)


class FiscalDocument(models.Model):
    _inherit = "l10n_br_fiscal.document"

    has_suggested_import_origin = fields.Boolean(
        compute="_compute_has_suggested_import_origin",
        help="Technical: some line of the imported document has an origin "
        "suggestion waiting for confirmation.",
    )

    edi_can_match_orders = fields.Boolean(
        compute="_compute_edi_can_match_orders",
        help="Technical: a purchase document imported from a partner and whose "
        "bill is not posted yet, the only kind that has an origin to choose.",
    )

    def _import_is_open(self):
        """The origin of the lines can still be decided: the document is not
        cancelled and no bill generated from it was posted."""
        self.ensure_one()
        return self.state_edoc not in CLOSED_DOCUMENT_STATES and not (
            self.sudo().move_ids.filtered(lambda move: move.state == "posted")
        )

    @api.depends("imported_document", "state_edoc", "issuer", "move_ids.state")
    def _compute_edi_can_match_orders(self):
        for document in self:
            document.edi_can_match_orders = bool(
                document.imported_document
                and document.issuer == DOCUMENT_ISSUER_PARTNER
                and document._import_is_open()
            )

    @api.depends("imported_document", "fiscal_line_ids.import_origin_state")
    def _compute_has_suggested_import_origin(self):
        for document in self:
            document.has_suggested_import_origin = bool(
                document.imported_document
                and "suggested"
                in document.fiscal_line_ids.mapped("import_origin_state")
            )

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

    def action_open_origin_match(self):
        """Open the reconciliation of the document with orders and quotations
        of its supplier."""
        self.ensure_one()
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "l10n_br_purchase_edi.document_match_action"
        )
        domain = [
            ("company_id", "=", self.company_id.id),
            # a source may have no partner (a purchase request without preferred
            # supplier): it can be the origin of the document of any supplier
            ("partner_id", "in", [self.partner_id.commercial_partner_id.id, False]),
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

    def _import_check_origins_decided(self):
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
