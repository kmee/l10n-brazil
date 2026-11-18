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
        result = super().write(vals)
        if vals.get("import_origin_state") == "resolved":
            self.filtered(
                lambda line: line.import_origin_state == "resolved"
            )._apply_import_origin_operation_line()
        return result

    def _apply_import_origin_operation_line(self):
        """The destination of the order goes into the imported line.

        The operation line of an imported line is the default one for the
        operation (the CFOP of the supplier, inverted, suggests the operation),
        and it does not know what the order was bought for. When the origin is
        decided, the line takes the operation line of the order line, which
        carries the destination (resale, use and consumption, fixed asset),
        unless the person already chose another one on the document line.
        """
        for line in self:
            wanted = line.import_purchase_line_id.sudo().fiscal_operation_line_id
            operation = line.fiscal_operation_id
            if (
                not wanted
                or wanted == line.fiscal_operation_line_id
                or wanted.fiscal_operation_id != operation
            ):
                continue
            default = operation.line_definition(
                company=line.company_id,
                partner=line.partner_id,
                product=line.product_id,
            )
            if line.fiscal_operation_line_id == default:
                line._set_operation_line_in_draft_bills(wanted)

    def _set_operation_line_in_draft_bills(self, operation_line):
        """Change the operation line of the line, and of the bill that is still
        a draft along with it.

        The bill line shares the fiscal line with the document (it delegates to
        it), so it reads the new operation line, but its accounting taxes were
        chosen for the old one. The change runs inside the synchronization of
        the bill, the same one that follows any edition of its lines, so the
        taxes are chosen again and the bill brings its tax lines and the amounts
        of its product lines along. A posted bill does not change: the warning
        of the bill points the person to it.
        """
        self.ensure_one()
        bill_lines = self.env["account.move.line"].search(
            [
                ("fiscal_document_line_id", "=", self.id),
                ("display_type", "=", "product"),
                ("move_id.state", "=", "draft"),
            ]
        )
        moves = bill_lines.move_id
        if not moves:
            self.fiscal_operation_line_id = operation_line
            return
        # the bill is balanced again only when all its lines are done
        moves = moves.with_context(check_move_validity=False)
        bill_lines = bill_lines.with_context(check_move_validity=False)
        with moves._sync_dynamic_lines({"records": moves}):
            self.fiscal_operation_line_id = operation_line
            for bill_line in bill_lines:
                bill_line.tax_ids = bill_line._get_computed_taxes()
        with moves.with_context(check_move_validity=True)._check_balanced(
            {"records": moves}
        ):
            pass

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
        # the fiscal profile that imports the file may have no access to the
        # purchase orders: the candidates are only read here
        return (
            empty.sudo()
            .search(domain)
            .filtered(
                lambda order_line: order_line.product_qty > order_line.qty_invoiced
            )
        )

    def _find_purchase_line_by_reference(self):
        self.ensure_one()
        document = self.document_id
        return (
            self.env["purchase.order.line"]
            .sudo()
            ._find_by_import_reference(
                document.company_id,
                document.partner_id.commercial_partner_id,
                (self.partner_order or "").strip(),
                self.partner_order_line,
                self.product_id,
            )
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
            self.env["purchase.order.line"]
            .sudo()
            .search_count(
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

    def _apply_import_match_source(self, source, trusted=False):
        """The match source of the import wizard grid becomes the origin of the
        line: resolved when the operator chose it (or the supplier declared it),
        otherwise a suggestion the person confirms in the review of the
        document."""
        result = super()._apply_import_match_source(source, trusted=trusted)
        if source.source_type == "po_line":
            order_line = self.env["purchase.order.line"].browse(source.id).exists()
            if order_line:
                self.write(
                    {
                        "import_purchase_line_id": order_line.id,
                        "import_origin_state": "resolved" if trusted else "suggested",
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
