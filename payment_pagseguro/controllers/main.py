# Copyright 2020 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

import requests
import werkzeug

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class PagseguroController(http.Controller):
    @http.route(
        ["/payment/pagseguro/s2s/create_json_3ds"],
        type="json",
        auth="public",
        csrf=False,
    )
    def pagseguro_s2s_create_json_3ds(self, verify_validity=False, **kwargs):
        if not kwargs.get("partner_id"):
            kwargs = dict(kwargs, partner_id=request.env.user.partner_id.id)

        token = (
            request.env["payment.acquirer"]
            .browse(int(kwargs.get("acquirer_id")))
            .s2s_process(kwargs)
        )

        if not token:
            res = {
                "result": False,
            }
        else:
            res = {
                "result": True,
                "id": token.id,
                "short_name": token.short_name,
                "3d_secure": False,
                "verified": False,
            }

            if verify_validity:
                token.validate()
                res["verified"] = token.verified

        return res

    @http.route(["/payment/pagseguro/public_key"], type="json", auth="public")
    def payment_pagseguro_get_public_key(self, **kwargs):
        """Get pagseguro API public key

        Makes a request to pagseguro with token auth to get the user public key.
        """
        acquirer_id = int(kwargs.get("acquirer_id"))
        acquirer = request.env["payment.acquirer"].browse(acquirer_id)

        api_url_public_keys = "https://%s/public-keys/" % (
            acquirer._get_pagseguro_api_url()
        )

        r = requests.post(
            api_url_public_keys,
            headers=acquirer.sudo()._get_pagseguro_api_headers(),
            json={"type": "card"},
        )

        if r.status_code == 401:
            raise werkzeug.exceptions.Unauthorized()
        elif str(r.status_code).startswith("40"):
            raise werkzeug.exceptions.BadRequest()

        res = r.json()
        public_key = res.get("public_key")

        return public_key

    @http.route("/notification-url", auth="public", type="json", methods=["POST"])
    def notification_url(self):
        """Receives Pagseguro Charge notification.
        Returns true on success and False on fail.
        Since this is a sensitive public route no further information is given.
        """
        params = request.jsonrequest
        charge_id = params.get("id")
        tx = (
            request.env["payment.transaction"]
            .sudo()
            .search([("acquirer_reference", "=", charge_id)])
        )
        tx.ensure_one()

        # Sends requests to pagseguro to check charge status instead of trusting
        # notification payload
        try:
            tx.pagseguro_check_transaction()
        except Exception as e:
            _logger.error(e)
            return False

        return True
