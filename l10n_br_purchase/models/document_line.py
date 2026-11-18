# Copyright 2026 KMEE - Luis Felipe Mileo <mileo@kmee.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class FiscalDocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    import_purchase_line_id = fields.Many2one(
        comodel_name="purchase.order.line",
        string="Purchase Order Line (origin)",
        copy=False,
        index=True,
        ondelete="set null",
        domain="['|', ('id', 'in', import_origin_candidate_ids),"
        " ('id', '=', import_purchase_line_id)]",
        help="Purchase order line this imported document line corresponds to. "
        "It is suggested from the order reference of the file (xPed and "
        "nItemPed) or from the only open order line of the supplier for the "
        "product, and it is the person who confirms or changes it. The vendor "
        "bill takes it from here.",
    )

    import_origin_state = fields.Selection(
        selection=[
            ("pending", "Pending"),
            ("suggested", "Suggested"),
            ("resolved", "Resolved"),
        ],
        string="Origin State",
        copy=False,
        index=True,
        help="Review of the origin of an imported line. Pending: the supplier "
        "has open order lines and none was chosen. Suggested: an automatic "
        "suggestion waits for confirmation. Resolved: a person chose it. "
        "Empty when there is nothing to choose from.",
    )

    import_origin_candidate_ids = fields.Many2many(
        comodel_name="purchase.order.line",
        compute="_compute_import_origin_candidate_ids",
        help="Technical: the open purchase order lines the origin can be chosen "
        "from (supplier of the document, product of the line, company, "
        "confirmed order with a balance to invoice).",
    )

    @api.depends(
        "document_id.partner_id",
        "document_id.company_id",
        "document_id.fiscal_operation_type",
        "product_id",
    )
    def _compute_import_origin_candidate_ids(self):
        for line in self:
            line.import_origin_candidate_ids = line._import_origin_candidates()

    def write(self, vals):
        if (
            "import_purchase_line_id" in vals
            and "import_origin_state" not in vals
            and not self.env.context.get("import_origin_suggestion")
        ):
            # a person picked (or cleared) the origin on the line
            vals = dict(
                vals,
                import_origin_state=(
                    "resolved" if vals["import_purchase_line_id"] else "pending"
                ),
            )
        return super().write(vals)

    def _import_origin_candidates(self):
        """Open purchase order lines of the supplier for the line product."""
        self.ensure_one()
        document = self.document_id
        partner = document.partner_id.commercial_partner_id
        empty = self.env["purchase.order.line"]
        if not partner or document.fiscal_operation_type != "in":
            return empty
        domain = [
            ("order_id.state", "in", ("purchase", "done")),
            ("order_id.company_id", "=", document.company_id.id),
            ("order_id.partner_id.commercial_partner_id", "=", partner.id),
            ("display_type", "=", False),
        ]
        if self.product_id:
            domain.append(("product_id", "=", self.product_id.id))
        return empty.search(domain).filtered(
            lambda order_line: order_line.product_qty > order_line.qty_invoiced
        )

    def _find_purchase_line_by_reference(self):
        self.ensure_one()
        document = self.document_id
        return self.env["purchase.order.line"]._find_by_import_reference(
            document.company_id,
            document.partner_id.commercial_partner_id,
            (self.partner_order or "").strip(),
            self.partner_order_line,
            self.product_id,
        )

    def _suggest_import_origin(self):
        """Suggest the origin of an imported line, never overriding a choice.

        The reference of the file (xPed and nItemPed) wins; without it, the
        only open order line of the supplier for the product is suggested;
        otherwise the line waits for a decision, and with nothing to choose
        from it has no origin state at all. Nothing is inferred by value.
        """
        for line in self:
            if (
                not line._is_imported()
                or line.import_origin_state == "resolved"
                or line.import_purchase_line_id
            ):
                continue
            order_line = line._find_purchase_line_by_reference()
            candidates = line._import_origin_candidates()
            if not order_line and len(candidates) == 1:
                order_line = candidates
            if order_line:
                state = "suggested"
            elif candidates or (
                line.document_id.partner_id
                and line.document_id.fiscal_operation_type == "in"
                and line._partner_has_open_order_lines()
            ):
                state = "pending"
            else:
                state = False
            line.with_context(import_origin_suggestion=True).write(
                {
                    "import_purchase_line_id": order_line.id or False,
                    "import_origin_state": state,
                }
            )

    def _partner_has_open_order_lines(self):
        self.ensure_one()
        document = self.document_id
        return bool(
            self.env["purchase.order.line"].search_count(
                [
                    ("order_id.state", "in", ("purchase", "done")),
                    ("order_id.company_id", "=", document.company_id.id),
                    (
                        "order_id.partner_id.commercial_partner_id",
                        "=",
                        document.partner_id.commercial_partner_id.id,
                    ),
                ],
                limit=1,
            )
        )

    def _apply_import_match_source(self, source):
        """The match source of the import wizard grid becomes a suggestion on
        the line: the person confirms it in the review of the document."""
        result = super()._apply_import_match_source(source)
        if source.source_type == "po_line":
            order_line = self.env["purchase.order.line"].browse(source.id).exists()
            if order_line:
                self.write(
                    {
                        "import_purchase_line_id": order_line.id,
                        "import_origin_state": "suggested",
                    }
                )
        return result

    def _apply_import_depara(self, *args, **kwargs):
        result = super()._apply_import_depara(*args, **kwargs)
        self._suggest_import_origin()
        return result

    @api.model
    def _import_origin_states(self):
        return ["pending", "suggested", "resolved"]
