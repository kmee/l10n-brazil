# Copyright 2020 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import base64
import pathlib

import requests

from odoo import _, api, fields, models
from odoo.exceptions import UserError

CERTIFICATE_PATH = str(pathlib.Path(__file__).parent.resolve()) + "/../static/binary/"


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

    client_id = fields.Char(string="Client ID")

    client_secret = fields.Char(string="Client Secret")

    crt_file = fields.Binary(string="CRT File")

    crt_filename = fields.Char()

    key_file = fields.Binary(string="KEY File")

    key_filename = fields.Char()

    seller_token = fields.Char(string="Seller token")

    pix_authentication = fields.Char(string="Pix authentication")

    state_validate = fields.Char(string="Validate credentials")

    @api.onchange("crt_file")
    def onchange_crt_file(self):
        if self.crt_file:
            with open(CERTIFICATE_PATH + self.crt_filename, "wb") as f:
                f.write(base64.b64decode(self.crt_file))

    @api.onchange("key_file")
    def onchange_key_file(self):
        if self.key_file:
            with open(CERTIFICATE_PATH + self.key_filename, "wb") as f:
                f.write(base64.b64decode(self.key_file))

    @api.multi
    def validate_credentials(self):
        url = self._get_pagseguro_api_url_pix()
        if self.crt_filename and self.key_filename:
            crt = CERTIFICATE_PATH + self.crt_filename
            key = CERTIFICATE_PATH + self.key_filename
        else:
            self.pix_authentication = None
            raise UserError(_("Please add CRT FILe and KEY File."))
        auth = (self.client_id, self.client_secret)
        data = {"grant_type": "client_credentials", "scope": "pix.write pix.read"}

        r = requests.post(
            url + "/pix/oauth2",
            auth=auth,
            data=data,
            cert=(crt, key),
        )

        data = r.json()
        if r.status_code == 200:
            self.pix_authentication = data["access_token"]
            self.state_validate = "Ok"
        else:
            self.pix_authentication = None
            self.state_validate = "Error"
            raise UserError(
                _(
                    f"Authentication failed.\n\n"
                    f" Code: {r.status_code}\n\n"
                    f"{r.text}"
                )
            )

    def get_installments_options(self):
        """ Get list of installment options available to compose the html tag """
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
