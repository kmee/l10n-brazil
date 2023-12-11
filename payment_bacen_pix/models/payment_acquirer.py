# Copyright 2022 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
import base64
import json
import logging
import os
import ssl

from uuid import uuid4
from requests_pkcs12 import Pkcs12Adapter

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
PIX_ENDPOINT_V2 = "pix/v2/cob/"
# TRANSACTION_STATUS_V2 = "v2/transactions/?id={}"
TRANSACTION_STATUS_V2 = "pix/v2/cob/{}"

BACENPIX = {
    "prod": PROD_URL,
    "test": SANDBOX_URL,
}

DIRNAME = os.path.dirname(__file__)

# TODO adicionar URLs de outros bancos -> verificar o padrão


class PaymentAcquirer(models.Model):

    _inherit = "payment.acquirer"

    provider = fields.Selection(
        selection_add=[(BACENPIX_PROVIDER, "Bacen (pix)")],
    )

    bacenpix_email_account = fields.Char("Email", groups="base.group_user")
    bacenpix_client_id = fields.Char("Client ID", groups="base.group_user")
    bacenpx_client_secret = fields.Char("Client Secret", groups="base.group_user")
    bacenpix_api_key = fields.Char(string="API KEY", groups="base.group_user")
    bacenpix_dev_app_key = fields.Char(string="Dev APP KEY", groups="base.group_user")
    bacen_pix_basic = fields.Char(string="Basic", groups="base.group_user")
    bacen_pix_key = fields.Char(string="PIX Key", groups="base.group_user")
    bacen_pix_expiration = fields.Integer(
        string="Bacen PIX Expiration",
        default=3600,
        help="Represents the lifetime of the charge, "
        "specified in seconds from the creation date",
        groups="base.group_user"
    )

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
        res["fees"].append("bacenpix")
        res["authorize"].append("bacenpix")
        res["tokenize"].append("bacenpix")
        return res


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

    def _bacenpix_params(self):
        return {
            "gw-dev-app-key": self.bacenpix_dev_app_key,
        }

    def _bacenpix_send_request(self, method, url, params, headers, data=None):
        with requests.Session() as session:
            bundle_path = os.path.join(str(os.path.normpath(DIRNAME + os.sep + os.pardir)), 'ca_certs_bundle')
            certified_file_name = '/tmp/' + uuid4().hex
            file_tmp = open(certified_file_name, 'wb')
            file_tmp.write(base64.b64decode(self.company_id.certificate_ecnpj_id.file))
            file_tmp.close()
            session.mount(
                url,
                Pkcs12Adapter(
                    pkcs12_filename=certified_file_name,
                    pkcs12_password=self.company_id.certificate_ecnpj_id.password,
                    ssl_protocol=ssl.PROTOCOL_TLSv1_2
                )
            )
            request = session.request(
                method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                verify=bundle_path
            )
            os.remove(certified_file_name)
            return request

    def _bacenpix_new_transaction(self, tx_id, payload):
        headers = self._bacenpix_header()
        url = werkzeug.urls.url_join(BACENPIX[self.environment], PIX_ENDPOINT_V2 + tx_id)
        params = self._bacenpix_params()
        response = self._bacenpix_send_request(
            "PUT",
            url,
            params,
            headers,
            payload
        )
        return response

    def _bacenpix_modify_pix(self, tx_id, payload):
        params = {
            "gw-dev-app-key": self.bacenpix_dev_app_key,
            "txid": tx_id
        }
        url = werkzeug.urls.url_join(BACENPIX[self.environment], TRANSACTION_STATUS_V2.format(tx_id))
        response = self._bacenpix_send_request(
            "PATCH",
            url,
            params=params,
            headers=self._bacenpix_header(),
            data=payload,
        )
        return response

    def _bacenpix_status_transaction(self, tx_bacen_id):
        url = werkzeug.urls.url_join(
                BACENPIX[self.environment], TRANSACTION_STATUS_V2.format(tx_bacen_id)
            )
        response = self._bacenpix_send_request(
            "GET",
            url,
            params=self._bacenpix_params(),
            headers=self._bacenpix_header(),
            data={},
        )
        return response

    def bacenpix_get_form_action_url(self):
        # 3. URL callback de feedback
        return "/payment/bacenpix/feedback"

    def _handle_bacenpix_webhook(self, data):
        """Webhook para processamento da transação"""
        pix = data.get('pix')
        transaction = pix and pix[0]
        txid = transaction.get('txid')

        transaction_id = self.env["payment.transaction"].search(
            [
                # "&",
                # "|",
                ("bacenpix_txid", "=", txid),
                # ("callback_hash", "=", txid),
                ("acquirer_id.provider", "=", BACENPIX_PROVIDER),
            ]
        )
        if not transaction_id:
            return False
        return transaction_id._bacenpix_validate_webhook(txid, data)
