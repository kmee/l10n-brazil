# Copyright 2026 KMEE - Luis Felipe Mileo <mileo@kmee.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from collections import defaultdict

from odoo import api, fields, models
from odoo.tools import float_compare

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    DOCUMENT_STATE_CANCEL,
    SITUACAO_EDOC_DENEGADA,
    SITUACAO_EDOC_INUTILIZADA,
)


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
        "suggestion waits for confirmation. Resolved: a person chose it, or the "
        "supplier declared it with no doubt (order and item of the file); "
        "resolved with no order line means the line has no order. "
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
        # one reading for all the lines, not one search for each of them
        pool = self._import_origin_pool()
        for line in self:
            line.import_origin_candidate_ids = line._import_origin_candidates(pool)

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

    def _import_origin_key(self):
        """(company, supplier) whose open order lines the line can take its
        origin from; False when it has none (an outgoing document, no partner)."""
        self.ensure_one()
        document = self.document_id
        partner = document.partner_id.commercial_partner_id
        if not partner or document.fiscal_operation_type != "in":
            return False
        return (document.company_id.id, partner.id)

    def _import_origin_pool(self):
        """The open order lines the lines of ``self`` can take their origin
        from, and the quantity the other imported documents already claimed on
        them.

        Everything is read once for all the lines (one search per supplier and
        company, one for the claims), so a big document does not make a search
        for each line. The fiscal profile that imports the file may have no
        access to the purchase orders: they are only read, with sudo.
        """
        order_line_model = self.env["purchase.order.line"].sudo()
        orders = {}
        for line in self:
            key = line._import_origin_key()
            if key and key not in orders:
                orders[key] = order_line_model.search(
                    [
                        ("order_id.state", "in", ("purchase", "done")),
                        ("order_id.company_id", "=", key[0]),
                        ("order_id.partner_id.commercial_partner_id", "=", key[1]),
                        ("display_type", "=", False),
                    ]
                )
        order_lines = order_line_model.browse()
        for found in orders.values():
            order_lines |= found
        claims = defaultdict(list)
        for claimant in self._import_claimants(order_lines):
            claims[claimant.import_purchase_line_id.id].append(
                (claimant.id, claimant._import_claimed_quantity())
            )
        return {"orders": orders, "claims": claims}

    @api.model
    def _import_claimants(self, order_lines):
        """The lines of imported documents that point to the order lines and
        have no bill yet: the bill counts what it takes as invoiced, but until
        it exists the document only holds the claim."""
        if not order_lines:
            return self.browse()
        claimants = (
            self.sudo()
            .search(
                [
                    ("import_purchase_line_id", "in", order_lines.ids),
                    ("document_id.imported_document", "=", True),
                    (
                        "document_id.state_edoc",
                        "not in",
                        (
                            DOCUMENT_STATE_CANCEL,
                            SITUACAO_EDOC_DENEGADA,
                            SITUACAO_EDOC_INUTILIZADA,
                        ),
                    ),
                ]
            )
            .filtered(
                lambda claimant: (
                    not claimant.document_id.move_ids.filtered(
                        lambda bill: bill.state != "cancel"
                    )
                )
            )
        )
        return claimants

    def _import_claimed_quantity(self, order_line=None):
        """The quantity of the line, in the unit of the order line it points to."""
        self.ensure_one()
        order_line = order_line or self.import_purchase_line_id
        if not self.uom_id or not order_line.product_uom:
            return self.quantity
        return self.uom_id._compute_quantity(
            self.quantity, order_line.product_uom, raise_if_failure=False
        )

    def _import_origin_balance(self, order_line, pool):
        """What is left of the order line for this line: the ordered quantity
        less what the bills already invoiced and less what the other imported
        documents, still without a bill, already claimed."""
        self.ensure_one()
        claimed = sum(
            quantity
            for claimant_id, quantity in pool["claims"].get(order_line.id, ())
            if claimant_id != self.id
        )
        return order_line.product_qty - order_line.qty_invoiced - claimed

    def _import_origin_candidates(self, pool=None):
        """Open purchase order lines of the supplier for the line product, with
        a balance left (the claims of the other imported documents counted)."""
        self.ensure_one()
        empty = self.env["purchase.order.line"]
        key = self._import_origin_key()
        if not key:
            return empty
        pool = pool or self._import_origin_pool()
        order_lines = pool["orders"].get(key, empty)
        if self.product_id:
            order_lines = order_lines.filtered(
                lambda order_line: order_line.product_id == self.product_id
            )
        return order_lines.filtered(
            lambda order_line: (
                float_compare(
                    self._import_origin_balance(order_line, pool),
                    0.0,
                    precision_rounding=order_line.product_uom.rounding,
                )
                > 0
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

        The reference of the file (xPed and nItemPed) wins and, when it points
        to exactly one open line with the product, the origin is resolved: the
        supplier declared it. Without it, the only open order line of the
        supplier for the product is just suggested; otherwise the line waits
        for a decision, and with nothing to choose from it has no origin state
        at all. Nothing is inferred by value.

        The open order lines are read once for all the lines, and what a line
        takes is counted for the next one.
        """
        lines = self.filtered(
            lambda line: (
                line._is_imported()
                and line.import_origin_state != "resolved"
                and not line.import_purchase_line_id
            )
        )
        pool = lines._import_origin_pool()
        for line in lines:
            order_line = line._find_purchase_line_by_reference()
            candidates = line._import_origin_candidates(pool)
            key = line._import_origin_key()
            if order_line:
                # the supplier declared the order and the item, and exactly one
                # open line of the order has the product: nothing left to decide
                state = "resolved"
            elif len(candidates) == 1:
                # the only open line of the supplier for the product is a
                # guess: a person confirms it
                order_line = candidates
                state = "suggested"
            elif candidates or (key and pool["orders"].get(key)):
                state = "pending"
            else:
                state = False
            line.with_context(import_origin_suggestion=True).write(
                {
                    "import_purchase_line_id": order_line.id or False,
                    "import_origin_state": state,
                }
            )
            if order_line:
                pool["claims"][order_line.id].append(
                    (line.id, line._import_claimed_quantity(order_line))
                )

    def _import_origin_has_balance(self, order_line):
        """True when the order line still has balance for this line: what the
        bills invoiced and what the other imported documents without a bill
        already claimed are discounted (the source preselected by the import is
        read from the open lines of the supplier, which do not know the claims)."""
        self.ensure_one()
        order_line = order_line.sudo()
        balance = self._import_origin_balance(order_line, self._import_origin_pool())
        return (
            float_compare(
                balance, 0.0, precision_rounding=order_line.product_uom.rounding
            )
            > 0
        )

    def _apply_import_match_source(self, source, trusted=False):
        """The match source of the import wizard grid becomes the origin of the
        line: resolved when the operator chose it (or the supplier declared it),
        otherwise a suggestion the person confirms in the review of the
        document."""
        result = super()._apply_import_match_source(source, trusted=trusted)
        if source.source_type == "po_line":
            order_line = self.env["purchase.order.line"].browse(source.id).exists()
            if order_line and (trusted or self._import_origin_has_balance(order_line)):
                self.write(
                    {
                        "import_purchase_line_id": order_line.id,
                        "import_origin_state": "resolved" if trusted else "suggested",
                    }
                )
        return result

    def _apply_import_depara(self, *args, **kwargs):
        result = super()._apply_import_depara(*args, **kwargs)
        if not self.env.context.get("import_origin_deferred"):
            # the import of a whole document suggests the origins once, after
            # the de-para of all its lines
            self._suggest_import_origin()
        # the de-para brings the operation line of the operation back to its
        # default: a decided origin takes the destination of its order again
        self.filtered(
            lambda line: line.import_origin_state == "resolved"
        )._apply_import_origin_operation_line()
        return result

    @api.model
    def _import_origin_states(self):
        return ["pending", "suggested", "resolved"]
