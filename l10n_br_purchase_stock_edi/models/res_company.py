# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    purchase_price_tolerance = fields.Float(
        string="Bill Price Tolerance (%)",
        default=0.0,
        help="A line whose unit price differs from the one of the purchase "
        "order line by more than this percentage (of the order price) is "
        "marked as divergent. It only warns: nothing is blocked.",
    )

    purchase_quantity_tolerance = fields.Float(
        string="Bill Quantity Tolerance (%)",
        default=0.0,
        help="A line whose quantity differs from the received quantity by more "
        "than this percentage (of the received quantity) is marked as "
        "divergent. It only warns: nothing is blocked.",
    )

    import_stock_entry_policy = fields.Selection(
        selection=[
            ("goods", "All goods"),
            ("storable", "Only products with inventory control"),
            ("none", "Do not ask"),
        ],
        string="Receipt on Invoice without Order",
        default="goods",
        required=True,
        help="Which products make the invoice of an imported purchase with no "
        "order ask for a receipt (or for the mark of a purchase or stock "
        "manager that nothing was received). All goods: every product that is "
        "not a service or a combo, with or without inventory control, because "
        "not counting the stock does not mean that the goods need not be "
        "received correctly. Only products with inventory control: the goods "
        "that are not counted go on. Do not ask: nothing is asked.",
    )

    _sql_constraints = [
        (
            "purchase_price_tolerance_positive",
            "CHECK(purchase_price_tolerance >= 0)",
            "The price tolerance cannot be negative.",
        ),
        (
            "purchase_quantity_tolerance_positive",
            "CHECK(purchase_quantity_tolerance >= 0)",
            "The quantity tolerance cannot be negative.",
        ),
    ]
