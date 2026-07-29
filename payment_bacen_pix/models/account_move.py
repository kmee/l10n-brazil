# Copyright 2023 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class AccountMove(models.Model):
    _inherit = "account.move"

    bacenpix_transaction_ids = fields.One2many(
        comodel_name="payment.transaction",
        inverse_name="bacenpix_invoice_id",
        string="Pix Charges",
        readonly=True,
    )
    bacenpix_charge_count = fields.Integer(
        string="Pix Charges Count",
        compute="_compute_bacenpix_charge_count",
    )

    @api.depends("bacenpix_transaction_ids")
    def _compute_bacenpix_charge_count(self):
        for move in self:
            move.bacenpix_charge_count = len(move.bacenpix_transaction_ids)

    def action_post(self):
        """Override of `account` to register the Pix charges of the invoice."""
        res = super().action_post()
        for move in self:
            payment_mode = move.payment_mode_id
            if (
                move.move_type in move.get_sale_types()
                and payment_mode.bacenpix_generate_on_post
                and payment_mode.bacenpix_charge_config_id
            ):
                move.action_bacenpix_generate_charges()
        return res

    def action_bacenpix_generate_charges(self):
        """Register one Pix charge for each unpaid installment of the invoice.

        The due date of the charge is the one of the installment, so an invoice
        paid in three times becomes three charges, each one payable on its own
        date.

        :return: None
        :raise UserError: If the invoice has no Pix payment mode.
        """
        for move in self:
            move._bacenpix_check_can_generate_charges()
            for line in move._bacenpix_get_installments():
                move._bacenpix_create_charge_for_installment(line)

    def _bacenpix_check_can_generate_charges(self):
        """Make sure the invoice can have Pix charges.

        :return: None
        :raise UserError: If the payment mode has no Pix charge configuration.
        """
        self.ensure_one()
        if self.state != "posted":
            raise UserError(
                _("Pix: The charges can only be registered for a posted invoice.")
            )
        if not self.payment_mode_id.bacenpix_charge_config_id:
            raise UserError(
                _(
                    "Pix: The payment mode of the invoice has no Pix charge "
                    "configuration."
                )
            )
        if not self.payment_mode_id.bacenpix_provider_id:
            raise UserError(
                _("Pix: The payment mode of the invoice has no Pix provider.")
            )

    def _bacenpix_get_installments(self):
        """Return the receivable lines that still wait for a payment.

        :return: The installments of the invoice.
        :rtype: recordset of `account.move.line`
        """
        self.ensure_one()
        charged_lines = self.bacenpix_transaction_ids.filtered(
            lambda t: t.state not in ("cancel", "error")
        ).mapped("bacenpix_move_line_id")
        return self.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
            and not line.reconciled
            and line not in charged_lines
        ).sorted("date_maturity")

    def _bacenpix_create_charge_for_installment(self, line):
        """Register the Pix charge of one installment.

        :param line: The receivable line to charge.
        :return: The transaction that holds the charge.
        :rtype: recordset of `payment.transaction`
        """
        self.ensure_one()
        transaction = self.env["payment.transaction"].create(
            self._bacenpix_prepare_charge_values(line)
        )
        transaction._bacenpix_create_charge()
        _logger.info(
            "registered the Pix charge %(txid)s of the invoice %(invoice)s due on "
            "%(due_date)s",
            {
                "txid": transaction.bacenpix_txid,
                "invoice": self.name,
                "due_date": transaction.bacenpix_due_date,
            },
        )
        return transaction

    def _bacenpix_prepare_charge_values(self, line):
        """Return the values of the transaction that charges an installment.

        :param line: The receivable line to charge.
        :return: The values of the transaction.
        :rtype: dict
        """
        self.ensure_one()
        provider = self.payment_mode_id.bacenpix_provider_id
        return {
            "provider_id": provider.id,
            "reference": self.env["payment.transaction"]._compute_reference(
                provider.code, prefix=line.name or self.name
            ),
            "amount": line.amount_residual,
            "currency_id": line.currency_id.id or self.currency_id.id,
            "partner_id": self.commercial_partner_id.id,
            "invoice_ids": [(6, 0, self.ids)],
            "bacenpix_invoice_id": self.id,
            "bacenpix_move_line_id": line.id,
            "bacenpix_charge_config_id": (
                self.payment_mode_id.bacenpix_charge_config_id.id
            ),
            "bacenpix_due_date": line.date_maturity,
        }

    def action_view_bacenpix_charges(self):
        """Open the Pix charges of the invoice."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Pix Charges"),
            "res_model": "payment.transaction",
            "view_mode": "tree,form",
            "domain": [("id", "in", self.bacenpix_transaction_ids.ids)],
        }
