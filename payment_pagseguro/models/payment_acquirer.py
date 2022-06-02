# Copyright 2020 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import logging
import tempfile
from pathlib import Path

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CERTIFICATE_PATH = str(Path(__file__).parent.resolve()) + "/../static/binary/"


class PaymentAcquirerPagseguro(models.Model):
    _inherit = "payment.acquirer"

    provider = fields.Selection(selection_add=[("pagseguro", "Pagseguro")])

    pagseguro_token = fields.Char(
        string="Pagseguro Token",
        required_if_provider="pagseguro",
        groups="base.group_user",
    )

    pagseguro_max_installments = fields.Integer(
        string="Pagseguro max installments",
        help="The maximum installments allowed by brands is 12",
        default=12,
    )

    pagseguro_client_id = fields.Char(string="Pagseguro Client ID")

    pagseguro_client_secret = fields.Char(string="Pagseguro Client Secret")

    pagseguro_crt_file = fields.Binary(string="Pagseguro CRT File")

    pagseguro_crt_filename = fields.Char()

    pagseguro_key_file = fields.Binary(string="Pagseguro KEY File")

    pagseguro_key_filename = fields.Char()

    pagseguro_tx_id = fields.Char(string="Transaction id")

    pagseguro_pix_acces_token = fields.Char()

    pagseguro_pix_authenticated = fields.Boolean(default=False)

    pagseguro_pix_expiration = fields.Integer(
        string="Pagseguro PIX Expiration",
        default=3600,
        help="Representa o tempo de vida da cobrança, "
        "especificado em segundos a partir da data de criação",
    )

    @api.onchange(
        "pagseguro_client_id",
        "pagseguro_client_secret",
        "pagseguro_crt_file",
        "pagseguro_key_file",
    )
    def onchange_client_credentials(self):
        self.pagseguro_pix_authenticated = False

    @staticmethod
    def _save_certificate(certificate_binary, suffix):
        """Save certificate in a temporary directory and return its path"""
        fd, path = tempfile.mkstemp(suffix=suffix)
        content = base64.b64decode(certificate_binary).decode("utf-8")

        with open(fd, "w") as f:
            f.write(content)

        return path

    @api.multi
    def pagseguro_pix_validate(self):
        """Validate Pagseguro PIX credentials

        Calls Pagseguro API to validate client credentials.
        """
        if not all(
            [
                self.pagseguro_crt_file,
                self.pagseguro_key_file,
                self.pagseguro_client_id,
                self.pagseguro_client_secret,
            ]
        ):
            raise UserError(_("Please fill your PIX credentials."))

        # Request parameters
        crt_path = self._save_certificate(self.pagseguro_crt_file, suffix=".pem")
        key_path = self._save_certificate(self.pagseguro_key_file, suffix=".key")
        url = self._get_pagseguro_api_url_pix()
        auth = (self.pagseguro_client_id, self.pagseguro_client_secret)
        data = {"grant_type": "client_credentials", "scope": "pix.write pix.read"}

        try:
            r = requests.post(
                url + "/pix/oauth2",
                auth=auth,
                data=data,
                cert=(crt_path, key_path),
            )
        except Exception as e:
            _logger.error(e)
            raise UserError(_("Authentication failed"))

        data = r.json()
        if r.status_code == 200:
            self.pagseguro_pix_acces_token = data.get("access_token")
            self.pagseguro_pix_authenticated = True
        else:
            self.pagseguro_pix_acces_token = False
            self.pagseguro_pix_authenticated = False
            error = data.get("error_messages")[0]
            raise UserError(
                _(
                    f"Authentication failed.\n\n"
                    f" Code: {error.get('code')}\n\n"
                    f"{error.get('description')}"
                )
            )

    def get_installments_options(self):
        """Get list of installment options available to compose the html tag"""
        return list(range(1, self.pagseguro_max_installments + 1))

    @api.multi
    def pagseguro_s2s_form_validate(self, data):
        """Validates user input"""
        self.ensure_one()
        # mandatory fields
        for field_name in ["cc_token", "cc_holder_name"]:
            if not data.get(field_name):
                return False
        return True

    @api.model
    def pagseguro_s2s_form_process(self, data):
        """Saves the payment.token object with data from PagSeguro server

        Cvc, number and expiry date card info should be empty by this point.
        """
        payment_token = (
            self.env["payment.token"]
            .sudo()
            .create(
                {
                    "cc_holder_name": data["cc_holder_name"],
                    "acquirer_ref": int(data["partner_id"]),
                    "acquirer_id": int(data["acquirer_id"]),
                    "partner_id": int(data["partner_id"]),
                    "pagseguro_card_token": data["cc_token"],
                    "pagseguro_payment_method": data["payment_method"],
                    "pagseguro_installments": int(data["installments"]),
                }
            )
        )
        return payment_token

    @api.model
    def pagseguro_pix_form_process(self, data):
        """Saves the payment.token object with data from PagSeguro server

        Cvc, number and expiry date card info should be empty by this point.
        """
        payment_token = (
            self.env["payment.token"]
            .sudo()
            .create(
                {
                    "acquirer_ref": int(data["partner_id"]),
                    "acquirer_id": int(data["acquirer_id"]),
                    "partner_id": int(data["partner_id"]),
                    "pagseguro_tx_id": data["tx_id"],
                }
            )
        )
        return payment_token

    @api.model
    def _get_pagseguro_api_url(self):
        """Get pagseguro API URLs used in all s2s communication

        Takes environment in consideration.
        """
        if self.environment == "test":
            return "sandbox.api.pagseguro.com"
        if self.environment == "prod":
            return "api.pagseguro.com"

    @api.multi
    def _get_pagseguro_api_headers(self):
        """Get pagseguro API headers used in all s2s communication

        Uses user token as authentication.
        """
        PAGSEGURO_HEADERS = {
            "Authorization": self.pagseguro_token,
            "Content-Type": "application/json",
            "x-api-version": "4.0",
        }

        return PAGSEGURO_HEADERS

    def _get_feature_support(self):
        """Get advanced feature support by provider.

        Each provider should add its technical in the corresponding
        key for the following features:
            * fees: support payment fees computations
            * authorize: support authorizing payment (separates
                         authorization and capture)
            * tokenize: support saving payment data in a payment.tokenize
                        object
        """
        res = super()._get_feature_support()
        res["authorize"].append("pagseguro")
        res["tokenize"].append("pagseguro")
        return res

    def _get_pagseguro_api_url_pix(self):
        """Get pagseguro API PIX URLs.

        Takes environment in consideration.
        """
        if self.environment == "test":
            return "https://secure.sandbox.api.pagseguro.com"
        if self.environment == "prod":
            return "https://secure.api.pagseguro.com"
