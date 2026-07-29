# Copyright 2023 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import logging
import pprint
import re
import uuid
from datetime import datetime, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment import utils as payment_utils

from ..const import PAYMENT_STATUS_MAPPING
from ..utils import redact_personal_data

_logger = logging.getLogger(__name__)

# The txid of a charge is limited to 26..35 alphanumeric characters by the Pix
# API, so the reference of the transaction cannot be used as is.
TXID_PATTERN = re.compile(r"^[a-zA-Z0-9]{26,35}$")


class PaymentTransaction(models.Model):
    _inherit = "payment.transaction"

    bacenpix_txid = fields.Char(
        string="Pix Transaction Id",
        help="The identifier of the charge on the Pix arrangement.",
        readonly=True,
    )
    bacenpix_qrcode = fields.Char(
        string="Pix Copy and Paste",
        help="The payload of the QR code, which the payer can also copy and "
        "paste in their banking application.",
        readonly=True,
    )
    bacenpix_location = fields.Char(
        string="Pix Location",
        help="The location of the payload registered with the PSP.",
        readonly=True,
    )
    bacenpix_expiration = fields.Datetime(
        string="Pix Expiration",
        help="The moment after which the charge can no longer be paid.",
        readonly=True,
    )
    bacenpix_charge_config_id = fields.Many2one(
        comodel_name="bacenpix.charge.config",
        string="Pix Charge Configuration",
        compute="_compute_bacenpix_charge_config_id",
        store=True,
        readonly=False,
        help="The kind of charge to register and its terms. Comes from the "
        "payment mode of the document being paid, or from the provider.",
    )
    bacenpix_charge_type = fields.Selection(
        related="bacenpix_charge_config_id.charge_type",
        string="Pix Charge Type",
        readonly=True,
    )
    bacenpix_invoice_id = fields.Many2one(
        comodel_name="account.move",
        string="Pix Invoice",
        help="The invoice whose installment this charge collects.",
        readonly=True,
        ondelete="cascade",
    )
    bacenpix_move_line_id = fields.Many2one(
        comodel_name="account.move.line",
        string="Pix Installment",
        help="The receivable line this charge collects.",
        readonly=True,
        ondelete="set null",
    )
    bacenpix_due_date = fields.Date(
        string="Pix Due Date",
        help="The date a charge with a due date (cobv) is due. Required by that "
        "kind of charge, and ignored by the immediate one.",
    )

    # === BUSINESS METHODS === #

    @api.depends("provider_id", "invoice_ids")
    def _compute_bacenpix_charge_config_id(self):
        """Take the charge configuration from the payment mode or the provider."""
        for transaction in self:
            if transaction.provider_code != "bacenpix":
                transaction.bacenpix_charge_config_id = False
                continue
            transaction.bacenpix_charge_config_id = (
                transaction._bacenpix_get_payment_mode().bacenpix_charge_config_id
                or transaction.provider_id.bacenpix_charge_config_id
            )

    def _bacenpix_get_charge_config(self):
        """Return the charge configuration that rules the transaction.

        The policy of the collection belongs to the payment mode of the
        document being paid, which is where the Brazilian localization keeps the
        terms of a charge. The configuration of the provider is the fallback for
        the payments that have no document behind them, such as an e-commerce
        checkout.

        :return: The configuration of the charge.
        :rtype: recordset of `bacenpix.charge.config`
        :raise ValidationError: If no configuration is found.
        """
        self.ensure_one()
        config = (
            self.bacenpix_charge_config_id
            or self._bacenpix_get_payment_mode().bacenpix_charge_config_id
            or self.provider_id.bacenpix_charge_config_id
        )
        if not config:
            raise ValidationError(
                _(
                    "Pix: No charge configuration is set on the payment mode nor "
                    "on the provider."
                )
            )
        return config

    def _bacenpix_get_payment_mode(self):
        """Return the payment mode of the document being paid.

        The invoice answers first; a payment made before the invoice exists
        falls back to the sale order, which carries the payment mode when
        `account_payment_sale` is installed. The module does not depend on it,
        so that a database without sales still installs.

        :return: The payment mode, if any.
        :rtype: recordset of `account.payment.mode`
        """
        self.ensure_one()
        invoice = self.invoice_ids[:1]
        if invoice.payment_mode_id:
            return invoice.payment_mode_id
        order = self.sale_order_ids[:1] if "sale_order_ids" in self._fields else None
        if order and "payment_mode_id" in order._fields:
            return order.payment_mode_id
        return self.env["account.payment.mode"]

    def _get_specific_rendering_values(self, processing_values):
        """Override of `payment` to return the values of the Pix charge.

        The charge is created on the PSP so that the payer already finds the QR
        code when the payment page opens.

        Note: self.ensure_one() from `_get_processing_values`

        :param dict processing_values: The generic processing values.
        :return: The provider-specific rendering values.
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != "bacenpix":
            return res

        if not self.bacenpix_txid:
            self._bacenpix_create_charge()

        return {
            "api_url": "/payment/bacenpix/qrcode",
            "reference": self.reference,
            "access_token": payment_utils.generate_access_token(
                self.reference, self.partner_id.id
            ),
        }

    def _bacenpix_charge_endpoint(self):
        """Return the endpoint of the charge, as told by its configuration.

        :return: `cob` for an immediate charge, `cobv` for one with a due date.
        :rtype: str
        """
        self.ensure_one()
        return self._bacenpix_get_charge_config().charge_type

    def _bacenpix_create_charge(self):
        """Create the charge on the PSP and store its QR code.

        A transaction with a due date is registered as a charge with a due date
        (`cobv`), which carries fine, interest and discount; without one, as an
        immediate charge (`cob`).

        :return: None
        """
        self.ensure_one()

        txid = uuid.uuid4().hex
        endpoint = self._bacenpix_charge_endpoint()
        if endpoint == "cobv":
            payload = self._bacenpix_prepare_charge_with_due_date_payload()
        else:
            payload = self._bacenpix_prepare_immediate_charge_payload()

        response_content = self.provider_id._bacenpix_make_request(
            f"/{endpoint}/{txid}", payload, method="PUT"
        )
        _logger.info(
            "charge creation response for transaction with reference %s:\n%s",
            self.reference,
            pprint.pformat(redact_personal_data(response_content)),
        )

        qr_code = response_content.get("pixCopiaECola")
        if not qr_code:
            raise ValidationError(
                _("Pix: The charge was created without a QR code payload.")
            )
        self.write(
            {
                "bacenpix_txid": response_content.get("txid") or txid,
                "bacenpix_qrcode": qr_code,
                "bacenpix_location": (response_content.get("loc") or {}).get("location")
                or response_content.get("location"),
                "bacenpix_expiration": self._bacenpix_compute_expiration(
                    response_content
                ),
            }
        )
        self._handle_notification_data("bacenpix", {"response": response_content})

    def _bacenpix_prepare_immediate_charge_payload(self):
        """Return the payload of an immediate charge.

        :return: The payload of the charge.
        :rtype: dict
        """
        self.ensure_one()

        payload = {
            "calendario": {"expiracao": self._bacenpix_get_charge_config().expiration},
            "valor": {"original": f"{self.amount:.2f}"},
            "chave": self.provider_id.sudo().bacenpix_key,
            "solicitacaoPagador": self.reference[:140],
        }
        debtor = self._bacenpix_prepare_debtor_payload()
        if debtor:
            payload["devedor"] = debtor
        return payload

    def _bacenpix_prepare_charge_with_due_date_payload(self):
        """Return the payload of a charge with a due date.

        The Pix arrangement requires the full address of the debtor on a charge
        with a due date, and accepts the fine, the interest and the discount
        configured on the provider.

        :return: The payload of the charge.
        :rtype: dict
        :raise ValidationError: If the debtor is not complete.
        """
        self.ensure_one()

        config = self._bacenpix_get_charge_config()
        if not self.bacenpix_due_date:
            raise ValidationError(
                _(
                    "Pix: The charge configuration %s registers a charge with a "
                    "due date, so the transaction needs one.",
                    config.display_name,
                )
            )
        return {
            "calendario": {
                "dataDeVencimento": self.bacenpix_due_date.strftime("%Y-%m-%d"),
                "validadeAposVencimento": config.validity_after_due_date,
            },
            "devedor": self._bacenpix_prepare_debtor_payload(with_address=True),
            "valor": self._bacenpix_prepare_charge_amount_payload(),
            "chave": self.provider_id.sudo().bacenpix_key,
            "solicitacaoPagador": self.reference[:140],
        }

    def _bacenpix_prepare_charge_amount_payload(self):
        """Return the `valor` part of a charge with a due date.

        :return: The amount payload, with the fine, interest and discount.
        :rtype: dict
        """
        self.ensure_one()

        config = self._bacenpix_get_charge_config()
        amount = {"original": f"{self.amount:.2f}"}
        if config.fine_value and config.fine_mode:
            amount["multa"] = {
                "modalidade": config.fine_mode,
                "valorPerc": f"{config.fine_value:.2f}",
            }
        if config.interest_value and config.interest_mode:
            amount["juros"] = {
                "modalidade": config.interest_mode,
                "valorPerc": f"{config.interest_value:.2f}",
            }
        if config.discount_value and config.discount_mode:
            # The discount holds until the due date of the charge.
            amount["desconto"] = {
                "modalidade": config.discount_mode,
                "descontoDataFixa": [
                    {
                        "data": self.bacenpix_due_date.strftime("%Y-%m-%d"),
                        "valorPerc": f"{config.discount_value:.2f}",
                    }
                ],
            }
        if config.rebate_value:
            amount["abatimento"] = {
                "modalidade": "1",
                "valorPerc": f"{config.rebate_value:.2f}",
            }
        return amount

    def _bacenpix_prepare_debtor_payload(self, with_address=False):
        """Return the `devedor` part of the payload of a charge.

        The Pix API only accepts a debtor with a valid CPF or CNPJ, so the
        section is left out when the partner has no tax id. A charge with a due
        date also requires the address of the debtor.

        :param bool with_address: Whether the address is required.
        :return: The debtor payload, or an empty dict.
        :rtype: dict
        :raise ValidationError: If the debtor of a charge with a due date is
                                not complete.
        """
        self.ensure_one()

        partner = self.partner_id
        tax_id = re.sub(r"\D", "", partner.vat or "")
        name = (self.partner_name or partner.name or "")[:200]
        debtor = {}
        if name and len(tax_id) == 11:
            debtor = {"cpf": tax_id, "nome": name}
        elif name and len(tax_id) == 14:
            debtor = {"cnpj": tax_id, "nome": name}

        if not with_address:
            return debtor

        address = {
            "logradouro": (partner.street or "")[:200],
            "cidade": (partner.city or "")[:200],
            "uf": partner.state_id.code or "",
            "cep": re.sub(r"\D", "", partner.zip or ""),
        }
        missing = [key for key, value in address.items() if not value]
        if not debtor or missing:
            raise ValidationError(
                _(
                    "Pix: A charge with a due date requires the name, the "
                    "CPF/CNPJ and the full address of %(partner)s. Missing: "
                    "%(missing)s.",
                    partner=partner.display_name,
                    missing=", ".join(missing) or _("CPF/CNPJ"),
                )
            )
        debtor.update(address)
        return debtor

    @staticmethod
    def _bacenpix_compute_expiration(response_content):
        """Return the moment the charge expires, out of its calendar.

        :param dict response_content: The charge as returned by the PSP.
        :return: The expiration of the charge.
        :rtype: datetime|bool
        """
        calendar = response_content.get("calendario") or {}
        due_date = calendar.get("dataDeVencimento")
        if due_date:
            # Uma cobrança com vencimento continua pagável por mais alguns dias.
            try:
                validity = int(calendar.get("validadeAposVencimento") or 0)
                return datetime.strptime(due_date, "%Y-%m-%d") + timedelta(
                    days=validity + 1
                )
            except (ValueError, TypeError):
                return False
        creation = calendar.get("criacao")
        expiration = calendar.get("expiracao")
        if not creation or not expiration:
            return False
        try:
            created_at = datetime.fromisoformat(creation.replace("Z", "+00:00"))
            created_at = created_at.replace(tzinfo=None)
            return created_at + timedelta(seconds=int(expiration))
        except (ValueError, TypeError):
            return False

    def _bacenpix_poll_charge(self):
        """Query the charge on the PSP and process its status.

        :return: None
        """
        self.ensure_one()

        if not self.bacenpix_txid:
            return
        response_content = self.provider_id._bacenpix_make_request(
            f"/{self._bacenpix_charge_endpoint()}/{self.bacenpix_txid}", method="GET"
        )
        _logger.info(
            "charge query response for transaction with reference %s:\n%s",
            self.reference,
            pprint.pformat(redact_personal_data(response_content)),
        )
        self._handle_notification_data("bacenpix", {"response": response_content})

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """Override of `payment` to find the transaction based on Pix data.

        :param str provider_code: The code of the provider that handled the tx.
        :param dict notification_data: The notification data sent by the provider.
        :return: The transaction if found.
        :rtype: recordset of `payment.transaction`
        :raise ValidationError: If no transaction is found matching the data.
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != "bacenpix" or len(tx) == 1:
            return tx

        txid = (notification_data.get("response") or {}).get("txid")
        if not txid:
            raise ValidationError(_("Pix: Received data with missing txid."))
        tx = self.search(
            [("bacenpix_txid", "=", txid), ("provider_code", "=", "bacenpix")]
        )
        if not tx:
            raise ValidationError(
                _("Pix: No transaction found matching txid %s.", txid)
            )
        return tx

    def _process_notification_data(self, notification_data):
        """Override of `payment` to process the transaction based on Pix data.

        Note: self.ensure_one()

        :param dict notification_data: The notification data sent by the provider.
        :return: None
        :raise ValidationError: If inconsistent data are received.
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != "bacenpix":
            return

        response_content = notification_data.get("response") or {}
        status = response_content.get("status")
        if not status:
            raise ValidationError(_("Pix: Received data with missing status."))

        # The end to end id of the payment identifies it on the arrangement.
        payments = response_content.get("pix") or []
        if payments and payments[0].get("endToEndId"):
            self.provider_reference = payments[0]["endToEndId"]

        if status in PAYMENT_STATUS_MAPPING["done"]:
            self._set_done()
            if self.operation == "refund":
                self.env.ref("payment.cron_post_process_payment_tx")._trigger()
        elif status in PAYMENT_STATUS_MAPPING["pending"]:
            if self.state != "pending":
                self._set_pending()
        elif status in PAYMENT_STATUS_MAPPING["cancel"]:
            self._set_canceled(state_message=status)
        else:
            _logger.warning(
                "received data with invalid status %(status)s for transaction "
                "with reference %(ref)s",
                {"status": status, "ref": self.reference},
            )
            self._set_error(_("Pix: Received data with invalid status: %s", status))

    def _cron_bacenpix_poll_pending_transactions(self):
        """Query the PSP for the charges that are still waiting for a payment.

        The webhook of the arrangement is the fastest way to be notified, but it
        requires the Odoo instance to be reachable by the PSP: this cron makes
        the module work without it.

        :return: None
        """
        pending_transactions = self.search(
            [
                ("provider_code", "=", "bacenpix"),
                ("state", "in", ("draft", "pending")),
                ("bacenpix_txid", "!=", False),
            ]
        )
        for transaction in pending_transactions:
            try:
                transaction._bacenpix_poll_charge()
            except ValidationError:
                _logger.warning(
                    "could not poll the charge of the transaction with reference %s",
                    transaction.reference,
                    exc_info=True,
                )
