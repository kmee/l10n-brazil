# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.tools import float_compare

from .stock_move import _PO_LINE_POSITION_SQL


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    purchase_ordered_qty = fields.Float(
        string="Ordered Quantity",
        compute="_compute_purchase_comparison",
        digits="Product Unit of Measure",
        help="Quantity of the purchase order line this vendor bill line is "
        "linked to, in the unit of the bill line.",
    )
    purchase_received_qty = fields.Float(
        string="Received Quantity",
        compute="_compute_purchase_comparison",
        digits="Product Unit of Measure",
        help="Quantity received for the purchase order line (done receipts, "
        "less the returns), in the unit of the bill line.",
    )
    purchase_price_unit = fields.Float(
        string="Order Unit Price",
        compute="_compute_purchase_comparison",
        digits="Product Price",
        help="Unit price of the purchase order line, in the unit and in the "
        "currency of the bill line.",
    )
    purchase_qty_difference = fields.Float(
        string="Quantity Difference",
        compute="_compute_purchase_comparison",
        digits="Product Unit of Measure",
        help="Billed quantity minus the received quantity that the other bills "
        "did not take yet (the lines of this same bill for the order line "
        "count together).",
    )
    purchase_price_difference = fields.Float(
        string="Price Difference",
        compute="_compute_purchase_comparison",
        digits="Product Price",
        help="Unit price of the bill minus the unit price of the order.",
    )
    purchase_divergent = fields.Boolean(
        string="Divergent",
        compute="_compute_purchase_comparison",
        help="The bill line differs from the order and the receipt by more "
        "than the tolerances of the company (price and quantity). It only "
        "warns: nothing is blocked.",
    )

    @api.model
    def _get_bill_matching_reference_sql(self, alias):
        """The order line the bill line is linked to, which the import decided
        (or a person chose on the bill), gives the reference to the order:
        (order name, 1-based position of the line), the same key the receipt
        has. It wins over what the supplier declared (xPed and nItemPed), which
        the document keeps untouched and which is only the fallback of the
        bill lines with no linked order line."""
        declared = super()._get_bill_matching_reference_sql(alias)
        decided = (
            "(SELECT LEFT(po_ref.name, 15) || '-' || "
            + _PO_LINE_POSITION_SQL.format(pol_alias="pol_ref")
            + "::varchar"
            " FROM purchase_order_line pol_ref"
            " JOIN purchase_order po_ref ON po_ref.id = pol_ref.order_id"
            f" WHERE pol_ref.id = {alias}.purchase_line_id)"
        )
        return f"COALESCE({decided}, {declared})"

    @api.depends(
        "purchase_line_id.product_qty",
        "purchase_line_id.product_uom",
        "purchase_line_id.qty_received",
        "purchase_line_id.invoice_lines.quantity",
        "purchase_line_id.invoice_lines.product_uom_id",
        "purchase_line_id.invoice_lines.move_id.state",
        "move_id.invoice_line_ids.purchase_line_id",
        "move_id.invoice_line_ids.quantity",
        "purchase_line_id.price_unit",
        "move_id.move_type",
        "move_id.invoice_date",
        "quantity",
        "price_unit",
        "product_uom_id",
        "currency_id",
        "company_id.purchase_price_tolerance",
        "company_id.purchase_quantity_tolerance",
    )
    def _compute_purchase_comparison(self):
        """Compare the bill line with its purchase order line and receipts.

        Read only and not stored: the receipts move after the bill is typed,
        and a stored value would need a recompute for each of them. The filter
        of the bill list searches through ``account.move._search_purchase_divergent``.
        """
        price_digits = self.env["decimal.precision"].precision_get("Product Price")
        for line in self:
            order_line = line.purchase_line_id
            values = {
                "purchase_ordered_qty": 0.0,
                "purchase_received_qty": 0.0,
                "purchase_price_unit": 0.0,
                "purchase_qty_difference": 0.0,
                "purchase_price_difference": 0.0,
                "purchase_divergent": False,
            }
            if order_line and line.move_id.is_purchase_document(include_receipts=True):
                order_uom = order_line.product_uom
                uom = line.product_uom_id or order_uom
                ordered = order_uom._compute_quantity(order_line.product_qty, uom)
                received = order_uom._compute_quantity(order_line.qty_received, uom)
                price = order_uom._compute_price(order_line.price_unit, uom)
                if order_line.currency_id != line.currency_id:
                    price = order_line.currency_id._convert(
                        price,
                        line.currency_id,
                        line.company_id,
                        line.move_id.invoice_date or fields.Date.context_today(line),
                    )
                # the bill is compared with what is still to be billed: the
                # received quantity less what the other bills (not cancelled)
                # already took. The lines of this same bill for the order line
                # (the supplier splitting the item by lot) count together.
                elsewhere = order_uom._compute_quantity(
                    order_line._quantity_billed_elsewhere(line.move_id), uom
                )
                billed = (
                    sum(
                        (other.product_uom_id or uom)._compute_quantity(
                            other.quantity, uom
                        )
                        for other in line.move_id.invoice_line_ids
                        if other.purchase_line_id == order_line
                    )
                    or line.quantity
                )
                qty_difference = billed - (received - elsewhere)
                price_difference = line.price_unit - price
                company = line.company_id
                quantity_tolerance = (
                    abs(received) * company.purchase_quantity_tolerance / 100
                )
                price_tolerance = abs(price) * company.purchase_price_tolerance / 100
                values.update(
                    {
                        "purchase_ordered_qty": ordered,
                        "purchase_received_qty": received,
                        "purchase_price_unit": price,
                        "purchase_qty_difference": qty_difference,
                        "purchase_price_difference": price_difference,
                        "purchase_divergent": float_compare(
                            abs(qty_difference),
                            quantity_tolerance,
                            precision_rounding=uom.rounding,
                        )
                        > 0
                        or float_compare(
                            abs(price_difference),
                            price_tolerance,
                            precision_digits=price_digits,
                        )
                        > 0,
                    }
                )
            line.update(values)
