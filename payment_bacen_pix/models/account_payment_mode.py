# Copyright 2023 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class AccountPaymentMode(models.Model):
    _inherit = "account.payment.mode"

    bacenpix_provider_id = fields.Many2one(
        comodel_name="payment.provider",
        string="Pix Provider",
        domain=[("code", "=", "bacenpix")],
        check_company=True,
        help="The Pix account that receives the charges of the documents using "
        "this payment mode.",
    )
    bacenpix_generate_on_post = fields.Boolean(
        string="Generate Pix charges on invoice",
        help="Register the Pix charges of the invoice, one per installment, "
        "when the invoice is posted.",
    )
    bacenpix_charge_config_id = fields.Many2one(
        comodel_name="bacenpix.charge.config",
        string="Pix Charge Configuration",
        help="The kind of Pix charge registered for the documents that use this "
        "payment mode, with its terms: an immediate charge, payable until it "
        "expires, or a charge with a due date, which carries fine, interest and "
        "discount.",
    )
