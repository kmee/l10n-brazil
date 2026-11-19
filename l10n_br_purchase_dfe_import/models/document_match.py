# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    DOCUMENT_STATE_CANCEL,
    DOCUMENT_STATE_DRAFT,
    SITUACAO_EDOC_DENEGADA,
    SITUACAO_EDOC_INUTILIZADA,
)

# Ids encode the source: id = SOURCE_COUNT * source id + source type. A module
# that adds a source (receipt, purchase request) takes the next type.
SOURCE_COUNT = 4
SOURCE_NOTE = 0
SOURCE_ORDER_LINE = 1


class DocumentMatch(models.Model):
    """Read model: what the system knows about where an imported document came
    from. Lines of the document waiting for an origin, and the lines of
    confirmed orders (with their balance) and of quotations of the supplier,
    side by side. Each module that knows another source adds a ``SELECT`` to
    ``_match_queries``.
    """

    _name = "l10n_br_purchase_dfe_import.match"
    _description = "Origin of an imported fiscal document"
    _auto = False
    _order = "product_id, kind, reference"

    kind = fields.Selection(
        selection=[
            ("note", "Invoice"),
            ("order", "Order"),
            ("quote", "Quotation"),
        ],
        readonly=True,
    )
    company_id = fields.Many2one(comodel_name="res.company", readonly=True)
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Supplier",
        readonly=True,
        help="Commercial partner of the document or of the order.",
    )
    product_id = fields.Many2one(comodel_name="product.product", readonly=True)
    description = fields.Char(readonly=True)
    declared_reference = fields.Char(
        string="Supplier Reference",
        readonly=True,
        help="Order and item the supplier declared in the file (xPed, nItemPed).",
    )
    uom_id = fields.Many2one(comodel_name="uom.uom", string="Unit", readonly=True)
    quantity = fields.Float(readonly=True, digits="Product Unit of Measure")
    open_quantity = fields.Float(
        string="Balance",
        readonly=True,
        digits="Product Unit of Measure",
        help="Order: ordered less invoiced less claimed by the other imported "
        "documents that have no bill yet.",
    )
    price_unit = fields.Float(string="Price", readonly=True, digits="Product Price")
    price_difference = fields.Float(
        compute="_compute_price_difference",
        digits="Product Price",
        help="Quotation price less the price of the line of the document being "
        "matched (context) for the same product, in the unit of the quotation.",
    )
    currency_id = fields.Many2one(comodel_name="res.currency", readonly=True)
    reference = fields.Char(readonly=True)
    date = fields.Date(readonly=True)
    line_state = fields.Selection(
        selection=[
            ("none", "No Open Order"),
            ("pending", "Pending"),
            ("suggested", "Suggested"),
            ("resolved", "Resolved"),
            ("no_order", "Without Order"),
            ("confirmed", "Confirmed"),
            ("draft", "Draft Quotation"),
            ("sent", "Quotation Sent"),
        ],
        string="Situation",
        readonly=True,
    )
    fiscal_document_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document", readonly=True
    )
    fiscal_line_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document.line", readonly=True
    )
    purchase_order_id = fields.Many2one(
        comodel_name="purchase.order", string="Purchase Order", readonly=True
    )
    purchase_line_id = fields.Many2one(
        comodel_name="purchase.order.line", string="Order Line", readonly=True
    )
    suggested_purchase_line_id = fields.Many2one(
        comodel_name="purchase.order.line",
        string="Origin Chosen",
        readonly=True,
        help="Order line the invoice line points to, suggested or resolved.",
    )

    @property
    def _table_query(self):
        return " UNION ALL ".join(self._match_queries())

    @api.model
    def _match_queries(self):
        """The ``SELECT`` of each source, all with the same columns."""
        return [self._match_note_query(), self._match_order_query()]

    @api.model
    def _match_note_query(self):
        return f"""
            SELECT
                {SOURCE_COUNT} * fl.id + {SOURCE_NOTE} AS id,
                'note' AS kind,
                fd.company_id AS company_id,
                rp.commercial_partner_id AS partner_id,
                fl.product_id AS product_id,
                fl.name AS description,
                NULLIF(CONCAT_WS(' / ', NULLIF(fl.partner_order, ''),
                    NULLIF(fl.partner_order_line, '')), '') AS declared_reference,
                fl.uom_id AS uom_id,
                fl.quantity AS quantity,
                fl.quantity AS open_quantity,
                fl.price_unit AS price_unit,
                rc.currency_id AS currency_id,
                COALESCE(fd.document_number, fd.document_key) AS reference,
                fd.document_date::date AS date,
                COALESCE(fl.import_origin_state, 'none') AS line_state,
                fd.id AS fiscal_document_id,
                fl.id AS fiscal_line_id,
                NULL::integer AS purchase_order_id,
                NULL::integer AS purchase_line_id,
                fl.import_purchase_line_id AS suggested_purchase_line_id
            FROM l10n_br_fiscal_document_line fl
            JOIN l10n_br_fiscal_document fd ON fd.id = fl.document_id
            JOIN res_partner rp ON rp.id = fd.partner_id
            JOIN res_company rc ON rc.id = fd.company_id
            WHERE fd.imported_document
                AND COALESCE(fd.fiscal_operation_type, 'in') = 'in'
                AND COALESCE(fd.edoc_purpose, '1') = '1'
                AND fd.state_edoc = '{DOCUMENT_STATE_DRAFT}'
                AND NOT EXISTS (
                    SELECT 1 FROM account_move am
                    WHERE am.fiscal_document_id = fd.id AND am.state != 'cancel'
                )
        """

    @api.model
    def _match_claims_query(self):
        """Quantity of each order line that imported documents without a bill
        resolved to, in the unit of the order line."""
        return f"""
            SELECT fl.import_purchase_line_id AS purchase_line_id,
                SUM(fl.quantity * CASE
                    WHEN fu.id IS NOT NULL AND fu.category_id = pu.category_id
                    THEN pu.factor / fu.factor ELSE 1 END) AS quantity
            FROM l10n_br_fiscal_document_line fl
            JOIN l10n_br_fiscal_document fd ON fd.id = fl.document_id
            JOIN purchase_order_line pl ON pl.id = fl.import_purchase_line_id
            LEFT JOIN uom_uom pu ON pu.id = pl.product_uom
            LEFT JOIN uom_uom fu ON fu.id = fl.uom_id
            WHERE fl.import_origin_state = 'resolved'
                AND fd.imported_document
                AND fd.state_edoc NOT IN ('{DOCUMENT_STATE_CANCEL}',
                    '{SITUACAO_EDOC_DENEGADA}', '{SITUACAO_EDOC_INUTILIZADA}')
                AND NOT EXISTS (
                    SELECT 1 FROM account_move am
                    WHERE am.fiscal_document_id = fd.id AND am.state != 'cancel'
                )
            GROUP BY fl.import_purchase_line_id
        """

    @api.model
    def _match_order_query(self):
        balance = "pl.product_qty - pl.qty_invoiced - COALESCE(claims.quantity, 0)"
        return f"""
            SELECT
                {SOURCE_COUNT} * pl.id + {SOURCE_ORDER_LINE} AS id,
                CASE WHEN po.state IN ('purchase', 'done')
                    THEN 'order' ELSE 'quote' END AS kind,
                po.company_id AS company_id,
                rp.commercial_partner_id AS partner_id,
                pl.product_id AS product_id,
                pl.name AS description,
                NULL::varchar AS declared_reference,
                pl.product_uom AS uom_id,
                pl.product_qty AS quantity,
                {balance} AS open_quantity,
                pl.price_unit AS price_unit,
                po.currency_id AS currency_id,
                po.name AS reference,
                po.date_order::date AS date,
                CASE WHEN po.state IN ('purchase', 'done')
                    THEN 'confirmed' ELSE po.state END AS line_state,
                NULL::integer AS fiscal_document_id,
                NULL::integer AS fiscal_line_id,
                po.id AS purchase_order_id,
                pl.id AS purchase_line_id,
                NULL::integer AS suggested_purchase_line_id
            FROM purchase_order_line pl
            JOIN purchase_order po ON po.id = pl.order_id
            JOIN res_partner rp ON rp.id = po.partner_id
            LEFT JOIN ({self._match_claims_query()}) claims
                ON claims.purchase_line_id = pl.id
            WHERE pl.display_type IS NULL
                AND (po.state IN ('draft', 'sent')
                    OR (po.state IN ('purchase', 'done') AND {balance} > 0))
        """

    @api.depends_context("match_document_id")
    @api.depends("kind", "price_unit", "uom_id", "product_id")
    def _compute_price_difference(self):
        document_id = self.env.context.get("match_document_id")
        notes = self.browse()
        if document_id:
            notes = self.search(
                [("kind", "=", "note"), ("fiscal_document_id", "=", document_id)]
            )
        for row in self:
            row.price_difference = 0.0
            if row.kind != "quote":
                continue
            same = notes.filtered(
                lambda note, row=row: note.product_id == row.product_id
            )
            if len(same) != 1:
                continue
            price = same.uom_id._compute_price(same.price_unit, row.uom_id)
            row.price_difference = row.price_unit - price

    # Actions ---------------------------------------------------------------

    def _split_selection(self):
        """Invoice lines, order lines and quotation lines of the selection, as
        records of the models they come from (read with sudo: the buyer and the
        fiscal profile do not read each other's models)."""
        rows = self.sudo()
        return (
            rows.filtered(lambda row: row.kind == "note").fiscal_line_id,
            rows.filtered(lambda row: row.kind == "order").purchase_line_id,
            rows.filtered(lambda row: row.kind == "quote").purchase_line_id,
        )

    @api.model
    def _editable_document(self, lines):
        """The one document of the lines, still open to change."""
        document = lines.document_id
        if len(document) != 1:
            raise UserError(_("Select the lines of one document at a time."))
        if document.state_edoc != DOCUMENT_STATE_DRAFT or document.move_ids.filtered(
            lambda move: move.state != "cancel"
        ):
            raise UserError(
                _("The document %s is not in draft or already has a bill.")
                % document.display_name
            )
        return document

    def action_match(self):
        """Resolve the origin of invoice lines to one confirmed order line."""
        notes, orders, quotes = self._split_selection()
        if quotes:
            raise UserError(
                _(
                    "A quotation cannot be matched until the buyer confirms the "
                    "order. Use Open Quotation."
                )
            )
        if not notes:
            raise UserError(_("Select the invoice lines to match."))
        if len(orders) != 1:
            raise UserError(_("Select one order line to match."))
        document = self._editable_document(notes)
        order_line = orders
        if order_line.order_id.state not in ("purchase", "done"):
            raise UserError(
                _("The order %s is not confirmed.") % order_line.order_id.name
            )
        if (
            order_line.company_id != document.company_id
            or order_line.order_id.partner_id.commercial_partner_id
            != document.partner_id.commercial_partner_id
        ):
            raise UserError(
                _("The order line is of another company or of another supplier.")
            )
        for line in notes:
            if line.product_id and line.product_id != order_line.product_id:
                raise UserError(
                    _(
                        "The product of the line %(line)s is not the product of "
                        "the order line.",
                        line=line.name,
                    )
                )
            if (
                line.uom_id
                and line.uom_id.category_id != order_line.product_uom.category_id
            ):
                raise UserError(
                    _(
                        "The unit of the line %(line)s does not convert to the "
                        "unit of the order line.",
                        line=line.name,
                    )
                )
        for line in notes:
            if not line.product_id:
                # the product of the order is the decision, learned as a de-para
                factor = (
                    line.uom_id._compute_quantity(1.0, order_line.product_uom)
                    if line.uom_id
                    else 1.0
                )
                line._apply_import_depara(
                    product=order_line.product_id,
                    uom=order_line.product_uom,
                    factor=factor,
                )
            line.write(
                {
                    "import_purchase_line_id": order_line.id,
                    "import_origin_state": "resolved",
                }
            )
        document.message_post(
            body=_(
                "Origin of %(count)s line(s) matched to the order %(order)s.",
                count=len(notes),
                order=order_line.order_id.name,
            )
        )
        return True

    def action_undo(self):
        """Take back a decision: the origin goes back to pending."""
        lines = self._split_selection()[0].filtered(
            lambda line: line.import_origin_state in ("resolved", "no_order")
        )
        if not lines:
            raise UserError(_("Select invoice lines with a decided origin."))
        document = self._editable_document(lines)
        lines.write(
            {"import_purchase_line_id": False, "import_origin_state": "pending"}
        )
        document.message_post(
            body=_("Origin of %(count)s line(s) undone.", count=len(lines))
        )
        return True

    def action_no_order(self):
        """Decide that the invoice lines have no order."""
        lines = self._split_selection()[0]
        if not lines:
            raise UserError(_("Select the invoice lines without an order."))
        document = self._editable_document(lines)
        lines.write(
            {"import_purchase_line_id": False, "import_origin_state": "no_order"}
        )
        document.message_post(
            body=_(
                "%(count)s line(s) marked as without purchase order.", count=len(lines)
            )
        )
        return True

    def action_open_quote(self):
        """Open the quotation for the buyer to confirm it."""
        order = self._split_selection()[2].order_id
        if len(order) != 1:
            raise UserError(_("Select the lines of one quotation."))
        return {
            "type": "ir.actions.act_window",
            "name": order.name,
            "res_model": "purchase.order",
            "res_id": order.id,
            "view_mode": "form",
        }

    def action_create_order(self):
        """Create a draft purchase order with the invoice lines selected."""
        notes, orders, quotes = self._split_selection()
        if orders or quotes or not notes:
            raise UserError(_("Select only invoice lines to create the order."))
        document = self._editable_document(notes)
        if not all(line.product_id for line in notes):
            raise UserError(_("Resolve the product of the selected lines first."))
        if notes.filtered(lambda line: line.import_origin_state == "resolved"):
            raise UserError(_("Undo the origin of the lines that already have one."))
        order = (
            self.env["purchase.order"]
            .with_company(document.company_id)
            .create(
                {
                    "partner_id": document.partner_id.id,
                    "company_id": document.company_id.id,
                    "origin": _("Fiscal document %s") % document.display_name,
                    "date_order": document.document_date or fields.Datetime.now(),
                    "order_line": [
                        fields.Command.create(self._prepare_order_line_vals(line))
                        for line in notes
                    ],
                }
            )
        )
        return {
            "type": "ir.actions.act_window",
            "name": order.name,
            "res_model": "purchase.order",
            "res_id": order.id,
            "view_mode": "form",
        }

    @api.model
    def _prepare_order_line_vals(self, line):
        """Quantity and price of the invoice line, in the unit of the product
        purchases."""
        product = line.product_id
        uom = product.uom_po_id or product.uom_id
        quantity, price = line.quantity, line.price_unit
        if line.uom_id and line.uom_id.category_id == uom.category_id:
            quantity = line.uom_id._compute_quantity(quantity, uom)
            price = line.uom_id._compute_price(price, uom)
        return {
            "product_id": product.id,
            "name": line.name,
            "product_qty": quantity,
            "product_uom": uom.id,
            "price_unit": price,
        }
