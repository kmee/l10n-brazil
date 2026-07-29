# Copyright 2023 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..const import (
    DEFAULT_EXPIRATION,
    DEFAULT_VALIDITY_AFTER_DUE_DATE,
    DISCOUNT_MODES,
    FINE_MODES,
    INTEREST_MODES,
)


class BacenPixChargeConfig(models.Model):
    """The kind of Pix charge to register and the terms that come with it.

    The Pix arrangement has two kinds of charge, and they are not
    interchangeable: the immediate charge (`cob`) is a QR code that stays
    payable for as long as its expiration says, which can be minutes or days,
    and carries no terms; the charge with a due date (`cobv`) is the one that
    behaves like a boleto, with fine, interest, discount and rebate, and stays
    payable after it is due.

    Which one to use is a decision of the merchant, per collection policy, so it
    is configured here instead of being guessed from the data of the payment.
    """

    _name = "bacenpix.charge.config"
    _description = "Pix Charge Configuration"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        comodel_name="res.company",
        help="Leave empty to make the configuration available to every company.",
    )
    charge_type = fields.Selection(
        selection=[
            ("cob", "Immediate charge (cob)"),
            ("cobv", "Charge with a due date (cobv)"),
        ],
        required=True,
        default="cob",
        help="The immediate charge is a QR code payable until it expires. The "
        "charge with a due date is the one that accepts fine, interest and "
        "discount, and stays payable after the due date.",
    )
    expiration = fields.Integer(
        string="Expiration (s)",
        default=DEFAULT_EXPIRATION,
        help="How long an immediate charge stays payable, in seconds. It can be "
        "as long as needed: 86400 for a day, 604800 for a week.",
    )
    validity_after_due_date = fields.Integer(
        string="Validity after due date (days)",
        default=DEFAULT_VALIDITY_AFTER_DUE_DATE,
        help="How many days a charge with a due date stays payable after it is " "due.",
    )
    fine_mode = fields.Selection(
        selection=FINE_MODES,
        default="2",
        help="How the fine of an overdue charge is calculated.",
    )
    fine_value = fields.Float(
        string="Fine",
        help="The amount or the percentage of the fine, as told by the mode.",
    )
    interest_mode = fields.Selection(
        selection=INTEREST_MODES,
        default="3",
        help="How the interest of an overdue charge is calculated.",
    )
    interest_value = fields.Float(
        string="Interest",
        help="The amount or the percentage of the interest, as told by the mode.",
    )
    discount_mode = fields.Selection(
        selection=DISCOUNT_MODES,
        help="How the discount for a payment before the due date is calculated.",
    )
    discount_value = fields.Float(
        string="Discount",
        help="The amount or the percentage of the discount, as told by the mode.",
    )
    rebate_value = fields.Float(
        string="Rebate",
        help="A fixed amount deducted from the charge, as agreed with the payer.",
    )

    @api.constrains("charge_type", "expiration", "validity_after_due_date")
    def _check_charge_type_values(self):
        for config in self:
            if config.charge_type == "cob" and config.expiration <= 0:
                raise ValidationError(
                    _("Pix: An immediate charge needs an expiration in seconds.")
                )
            if config.charge_type == "cobv" and config.validity_after_due_date < 0:
                raise ValidationError(
                    _("Pix: The validity after the due date cannot be negative.")
                )

    @api.constrains("charge_type", "fine_value", "interest_value", "discount_value")
    def _check_terms_of_an_immediate_charge(self):
        """An immediate charge has no place for fine, interest or discount."""
        for config in self:
            if config.charge_type != "cob":
                continue
            if any((config.fine_value, config.interest_value, config.discount_value)):
                raise ValidationError(
                    _(
                        "Pix: An immediate charge (cob) does not carry fine, "
                        "interest nor discount. Use a charge with a due date "
                        "(cobv) for that."
                    )
                )
