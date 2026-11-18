# Copyright (C) 2009  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, fields, models


class Company(models.Model):
    _inherit = "res.company"

    purchase_fiscal_operation_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.operation",
        string="Default Fiscal Operation for Purchase",
        domain=[("state", "=", "approved"), ("fiscal_type", "=", "purchase")],
    )

    purchase_invoicing_policy = fields.Selection(
        selection=[
            ("purchase_order", _("Purchase Order")),
            ("stock_picking", _("Stock Picking")),
        ],
        default="purchase_order",
    )

    purchase_price_tolerance = fields.Float(
        string="Bill Price Tolerance (%)",
        default=0.0,
        help="A vendor bill line whose unit price differs from the one of the "
        "purchase order line by more than this percentage (of the order "
        "price) is marked as divergent. It only warns: nothing is blocked.",
    )

    purchase_quantity_tolerance = fields.Float(
        string="Bill Quantity Tolerance (%)",
        default=0.0,
        help="A vendor bill line whose quantity differs from the received "
        "quantity by more than this percentage (of the received quantity) is "
        "marked as divergent. It only warns: nothing is blocked.",
    )

    _sql_constraints = [
        (
            "purchase_price_tolerance_positive",
            "CHECK(purchase_price_tolerance >= 0)",
            "The price tolerance of the vendor bill cannot be negative.",
        ),
        (
            "purchase_quantity_tolerance_positive",
            "CHECK(purchase_quantity_tolerance >= 0)",
            "The quantity tolerance of the vendor bill cannot be negative.",
        ),
    ]
