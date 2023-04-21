# Copyright 2022 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json
import logging

import requests
import werkzeug.urls

from odoo import fields, models

_logger = logging.getLogger(__name__)

BACENPIX_PROVIDER = "bacenpix"

SANDBOX_GET_TOKEN_URL = "https://oauth.hm.bb.com.br/"
PROD_GET_TOKEN_URL = "https://oauth.bb.com.br/"

BACENPIX_GET_TOKEN = {"prod": PROD_GET_TOKEN_URL, "test": SANDBOX_GET_TOKEN_URL}

SANDBOX_URL = "https://api.hm.bb.com.br/"
PROD_URL = "https://api-pix.bb.com.br/"

AUTH_ENDPOINT = "oauth/token"

PIX_ENDPOINT_V1 = "pix/v1/cob/"

BACENPIX = {
    "prod": PROD_URL,
    "test": SANDBOX_URL,
}

# TODO adicionar URLs de outros bancos -> verificar o padrão


class PaymentAcquirer(models.Model):

    _inherit = "payment.acquirer"

    provider = fields.Selection(
        selection_add=[(BACENPIX_PROVIDER, "Bacen (pix)")],
        # ondelete={BACENPIX_PROVIDER: "set default"},
    )

    bacenpix_email_account = fields.Char("Email", groups="base.group_user")
    bacenpix_client_id = fields.Char("Client ID", groups="base.group_user")
    bacenpx_client_secret = fields.Char("Client Secret", groups="base.group_user")
    bacenpix_api_key = fields.Char(string="API KEY", groups="base.group_user")
    bacenpix_dev_app_key = fields.Char(string="Dev APP KEY", groups="base.group_user")
    bacen_pix_basic = fields.Char(string="Basic", groups="base.group_user")
    bacen_pix_key = fields.Char(
        string="PIX Key",
        help="Set your Pix key that you registered with your bank.",
        groups="base.group_user"
    )
    bacen_pix_expiration = fields.Integer(
        string="Bacen PIX Expiration",
        default=3600,
        help="Represents the lifetime of the charge, "
        "specified in seconds from the creation date",
        groups="base.group_user"
    )

    def bacenpix_compute_fees(self, amount, currency_id, country_id):
        """Compute fees

        :param float amount: the amount to pay
        :param integer country_id: an ID of a res.country, or None. This is
                                   the customer's country, to be compared to
                                   the acquirer company country.
        :return float fees: computed fees
        """
        fees = 0.0
        if self.fees_active:
            country = self.env["res.country"].browse(country_id)
            if country and self.company_id.sudo().country_id.id == country.id:
                percentage = self.fees_dom_var
                fixed = self.fees_dom_fixed
            else:
                percentage = self.fees_int_var
                fixed = self.fees_int_fixed
            fees = (percentage / 100.0 * amount + fixed) / (1 - percentage / 100.0)
        return fees

    def bacen_pix_get_token(self):
        querystring = {
            "grant_type": "client_credentials",
            "scope": "cob.write cob.read cobv.write cobv.read"
            + "lotecobv.write lotecobv.read pix.write pix.read webhook.read"
            + "webhook.write payloadlocation.write payloadlocation.read",
            "client_id": self.bacenpix_client_id,
            "client_secret": self.bacenpx_client_secret,
        }

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": self.bacen_pix_basic,
        }
        response = requests.request(
            "POST",
            werkzeug.urls.url_join(BACENPIX_GET_TOKEN[self.environment], AUTH_ENDPOINT),
            params=querystring,
            headers=headers,
        )
        if response.status_code != 200:
            self.bacenpix_api_key = "Error"
        else:
            response_data = json.loads(json.dumps(response.json()))
            self.bacenpix_api_key = (
                response_data["token_type"] + " " + response_data["access_token"]
            )

    def _bacenpix_header(self):
        self.bacen_pix_get_token()

        return {
            "Authorization": self.bacenpix_api_key,
            "Content-Type": "application/json",
        }

    def _bacenpix_new_transaction(self, tx_id, payload):
        params = {
            "gw-dev-app-key": self.bacenpix_dev_app_key,
            "txid": tx_id
        }
        response = requests.request(
            "PUT",
            werkzeug.urls.url_join(BACENPIX[self.environment], PIX_ENDPOINT_V1),
            params=params,
            headers=self._bacenpix_header(),
            data=payload,
        )
        return response

    def _bacenpix_status_transaction(self, txid):
        params = {
            "gw-dev-app-key": self.bacenpix_dev_app_key,
            # "txid": txid
        }
        response = requests.request(
            "GET",
            werkzeug.urls.url_join(
                BACENPIX[self.environment], PIX_ENDPOINT_V1) + txid,
            params=params,    
            headers=self._bacenpix_header(),
            data={},
        )
        return response

    def bacenpix_get_form_action_url(self):
        # 3. URL callback de feedback
        return "/payment/bacenpix/feedback"

    def _handle_bacenpix_webhook(self, tx_reference, jsonrequest):
        """Webhook para processamento da transação"""
        transaction_id = self.env["payment.transaction"].search(
            [
                ("callback_hash", "=", tx_reference),
                ("acquirer_id.provider", "=", BACENPIX_PROVIDER),
            ]
        )
        if not transaction_id:
            return False
        return transaction_id._bacenpix_validate_webhook(tx_reference, jsonrequest)
