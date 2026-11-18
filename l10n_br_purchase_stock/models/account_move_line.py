# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.tools import float_compare


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
        help="Billed quantity minus the received quantity.",
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

    @api.depends(
        "purchase_line_id.product_qty",
        "purchase_line_id.product_uom",
        "purchase_line_id.qty_received",
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
                qty_difference = line.quantity - received
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
