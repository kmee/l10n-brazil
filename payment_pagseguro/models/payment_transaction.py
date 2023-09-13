# Copyright 2020 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import datetime
import logging
import pprint
from xml.etree import ElementTree

import requests
from erpbrasil.base.misc import punctuation_rm

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentTransactionPagseguro(models.Model):
    _inherit = "payment.transaction"

    pagseguro_s2s_capture_link = fields.Char(
        string="Pagseguro Capture Link",
        required=False,
    )
    pagseguro_s2s_void_link = fields.Char(
        string="Pagseguro Cancel Link",
        required=False,
    )
    pagseguro_s2s_check_link = fields.Char(
        string="Pagseguro Check Link",
        required=False,
    )

    pagseguro_boleto_pdf_link = fields.Char(string="Pagseguro boleto pdf link")

    pagseguro_boleto_image_link = fields.Char(string="Pagseguro boleto image link")

    pagseguro_boleto_barcode = fields.Char(string="Pagseguro boleto barcode")

    pagseguro_pix_copy_paste = fields.Char(string="Pagseguro PIX copy and paste code")

    pagseguro_pix_image_link = fields.Char(string="Pagseguro PIX image link")

    def _set_transaction_state(self, res):
        """Change transaction state based on Pagseguro status"""
        pagseguro_status = res.get("status")

        if pagseguro_status == "PAID":
            self._set_transaction_done()
        elif pagseguro_status in ["AUTHORIZED", "WAITING"]:
            self._set_transaction_authorized()
        elif pagseguro_status in ["CANCELED", "DECLINED"]:
            self._set_transaction_cancel()

    def _set_transaction_state_pix(self, pagseguro_status):
        """Change transaction state Pix based on Pagseguro status"""

        if pagseguro_status == 4:
            self.done = self._set_transaction_done()
        elif pagseguro_status == 3:
            self._set_transaction_authorized()
        elif pagseguro_status in [1, 2, 5, 9]:
            self._set_transaction_pending()
        elif pagseguro_status in [6, 7, 8]:
            self._set_transaction_cancel()

    @api.multi
    def _create_pagseguro_pix_charge(self, cert):
        if not self.acquirer_id.pagseguro_pix_acces_token:
            return {"status": "INVALID", "error": "No Access Token"}

        url = self.acquirer_id._get_pagseguro_api_url_pix()
        auth_token = self.acquirer_id.pagseguro_pix_acces_token
        header = {
            "Authorization": "Bearer " + auth_token,
            "Content-Type": "application/json",
        }

        cpf = str(self.payment_token_id.partner_id.cnpj_cpf)
        payload = {
            "calendario": {"expiracao": str(self.acquirer_id.pagseguro_pix_expiration)},
            "devedor": {
                "cpf": punctuation_rm(cpf),
                "nome": str(self.payment_token_id.partner_id.name),
            },
            "valor": {"original": "%.2f" % self.amount},
            "chave": str(self.acquirer_id.pagseguro_pix_key),
            "solicitacaoPagador": "Compra online.",
        }

        try:
            r = requests.put(
                url + "/instant-payments/cob/" + self.payment_token_id.pagseguro_tx_id,
                json=payload,
                cert=(cert[0], cert[1]),
                headers=header,
            )
        except Exception as e:
            _logger.error(e)
            raise ValidationError(_("Failed to send request to Pagseguro"))

        res = r.json()
        _logger.info(
            "_create_pagseguro_charge: Values received:\n%s",
            self.pprint_filtered_response(res),
        )

        return res

    def _create_pagseguro_charge(self):
        """Creates the s2s payment.

        Uses encrypted credit card.
        """
        api_url_charge = "https://%s/charges" % (
            self.acquirer_id._get_pagseguro_api_url()
        )

        self.payment_token_id.active = False

        _logger.info(
            "_create_pagseguro_charge: Sending values to URL %s", api_url_charge
        )
        r = requests.post(
            api_url_charge,
            json=self._get_pagseguro_charge_params(),
            headers=self.acquirer_id._get_pagseguro_api_headers(),
        )
        res = r.json()
        _logger.info(
            "_create_pagseguro_charge: Values received:\n%s",
            self.pprint_filtered_response(res),
        )
        return res

    @api.multi
    def pagseguro_pix_do_transaction(self):
        self.ensure_one()
        cert = self.acquirer_id.get_cert()
        charge = self._create_pagseguro_pix_charge(cert)
        return self._pagseguro_pix_validate_tree(charge)

    def _pagseguro_pix_validate_tree(self, charge):
        self.ensure_one()

        self.pagseguro_pix_copy_paste = charge.get("pixCopiaECola")
        self.pagseguro_pix_image_link = charge.get("urlImagemQrCode")

        if charge.get("status") == "ATIVA":
            self.log_transaction(
                reference=charge.get("txid"), message=charge.get("status")
            )
            self._set_transaction_authorized()
            self.payment_token_id.verified = True
            return {"result": True, "location": charge.get("loc", {}).get("location")}

        elif charge.get("status") == "INVALID":
            return {"result": False, "error": charge.get("error")}

        else:
            return {
                "result": False,
                "error": f"{charge.get('title')}: {charge.get('detail')}",
            }

    @api.model
    def pagseguro_search_payment_pix(self, params):
        acquirer_id = self.env.ref(
            "payment_pagseguro.payment_acquirer_pagseguro"
        ).sudo()
        notification_code = params["notificationCode"]
        cert = acquirer_id.get_cert()
        url = acquirer_id._get_pagseguro_api_url_pix()
        auth_token = self.acquirer_id.pagseguro_token
        params = {"email": acquirer_id.pagseguro_email, "token": auth_token}
        header = {
            "Content-Type": "application/xml",
        }
        r = requests.get(
            url + "/v3/transactions/notifications/" + notification_code,
            cert=(cert[0], cert[1]),
            headers=header,
            json=params,
        )
        if r.status_code == 200:
            string_xml = r.content
            xml_tree = ElementTree.fromstring(string_xml)
            code = xml_tree.find("code").text
            status = xml_tree.find("status").text
            transaction_id = self.search([("acquirer_reference", "=", code)])
            transaction_id._set_transaction_state_pix(status)

            _logger.info(
                "pagseguro_search_payment_pix: Transaction %s has status %s"
                % (code, status)
            )
        else:
            _logger.error("Failed to receive Webhook notification.")

    @api.multi
    def pagseguro_s2s_do_transaction(self):
        self.ensure_one()
        result = self._create_pagseguro_charge()

        return self._pagseguro_s2s_validate_tree(result)

    @api.multi
    def pagseguro_s2s_capture_transaction(self):
        """Captures an authorized transaction."""
        currencies = self.sale_order_ids.currency_id.mapped(
            "name"
        )  # Add all sale orders currencies
        currencies += self.invoice_ids.currency_id.mapped(
            "name"
        )  # Add all invoices currencies
        if any([currency != "BRL" for currency in currencies]):
            raise ValidationError(
                _(
                    "Please check if all related sale orders "
                    "and invoices are in BRL "
                    "currency (supported by pagseguro)."
                )
            )

        _logger.info(
            "pagseguro_s2s_capture_transaction: Sending values to URL %s",
            self.pagseguro_s2s_capture_link,
        )
        r = requests.post(
            self.pagseguro_s2s_capture_link,
            headers=self.acquirer_id._get_pagseguro_api_headers(),
            json=self._get_pagseguro_charge_params(),
        )
        res = r.json()
        _logger.info(
            "pagseguro_s2s_capture_transaction: Values received:\n%s",
            self.pprint_filtered_response(res),
        )

        if (
            type(res) == dict
            and res.get("payment_response")
            and res.get("payment_response").get("message") == "SUCESSO"
        ):
            # apply result
            self.log_transaction(res["id"], res["payment_response"]["message"])
            self._set_transaction_done()
            self.execute_callback()
        else:
            self.log_transaction(
                reference=res["error_messages"][0]["code"],
                message=res["error_messages"][0]["message"],
            )

    @api.multi
    def pagseguro_s2s_void_transaction(self):
        """Voids an authorized transaction."""
        _logger.info(
            "pagseguro_s2s_void_transaction: Sending values to URL %s",
            self.pagseguro_s2s_void_link,
        )
        headers = {
            "Authorization": self.acquirer_id.pagseguro_token,
            "x-api-version": "4.0",
        }

        params = {
            "charge_id": self.id,
            "amount": {
                "value": int(self.amount * 100),
            },
        }

        r = requests.post(
            self.pagseguro_s2s_void_link,
            headers=headers,
            json=params,
        )
        res = r.json()
        _logger.info(
            "pagseguro_s2s_void_transaction: Values received:\n%s",
            self.pprint_filtered_response(res),
        )

        if (
            type(res) == dict
            and res.get("payment_response")
            and res.get("payment_response").get("message") == "SUCESSO"
        ):
            # apply result
            self.log_transaction(res["id"], res["payment_response"]["message"])
            self._set_transaction_cancel()
        else:
            self.log_transaction(
                reference=res["error_messages"][0]["code"],
                message=res["error_messages"][0]["message"],
            )

    @api.multi
    def _pagseguro_s2s_validate_tree(self, tree):
        """Validates the transaction.

        This method updates the payment.transaction object describing the
        actual transaction outcome.
        Also saves get/capture/void links sent by pagseguro to make it easier to
        perform the operations.

        """
        self.ensure_one()
        if self.state != "draft":
            _logger.info(
                "PagSeguro: trying to validate an already validated tx (ref %s)",
                self.reference,
            )
            return True

        payment = tree.get("payment_response", {})
        if payment:
            code = payment.get("code")
            if code == "20000":
                self.log_transaction(reference=tree.get("id"), message="")

            # store capture and void links for future manual operations
            self.store_links(tree)
            self._set_transaction_state(tree)

            # setting transaction to authorized - must match Pagseguro
            # payment using the case without automatic capture
            self._set_transaction_authorized()
            self.execute_callback()
            if self.payment_token_id:
                self.payment_token_id.verified = True
                self._validate_tree_message(tree)
                return True
            else:
                self._validate_tree_message(tree)
                return False

        self._validate_tree_message(tree)

        return False

    def _store_links_credit(self, tree):
        for link in tree.get("links"):
            if link.get("rel") == "SELF":
                self.pagseguro_s2s_check_link = link.get("href")
            if link.get("rel") == "CHARGE.CAPTURE":
                self.pagseguro_s2s_capture_link = link.get("href")
            if link.get("rel") == "CHARGE.CANCEL":
                self.pagseguro_s2s_void_link = link.get("href")

    def _store_links_boleto(self, tree):
        for link in tree.get("links"):
            if link.get("media") == "application/json":
                self.pagseguro_s2s_check_link = link.get("href")
            elif link.get("media") == "application/pdf":
                self.pagseguro_boleto_pdf_link = link.get("href")
            elif link.get("media") == "image/png":
                self.pagseguro_boleto_image_link = link.get("href")

    def _save_barcode(self, tree):
        barcode = tree.get("payment_method", {}).get("boleto", {}).get("barcode")
        self.pagseguro_boleto_barcode = barcode

    def store_links(self, tree):
        if self.payment_token_id.pagseguro_payment_method == "CREDIT_CARD":
            self._store_links_credit(tree)
        elif self.payment_token_id.pagseguro_payment_method == "BOLETO":
            self._store_links_boleto(tree)
            self._save_barcode(tree)

    @api.multi
    def _validate_tree_message(self, tree):
        if tree.get("message"):
            error = tree.get("message")
            _logger.warning(error)
            self.sudo().write(
                {
                    "state_message": error,
                    "acquirer_reference": tree.get("id"),
                    "date": fields.datetime.now(),
                }
            )
            self._set_transaction_cancel()

    @api.multi
    def _get_pagseguro_credit_card_charge_params(self):
        """
        Returns pagseguro credit card charge params.
        """
        return {
            "reference_id": str(self.payment_token_id.acquirer_id.id),
            "description": self.display_name[:13],
            "amount": {
                "value": int(
                    self.amount * 100
                ),  # Charge is in BRL cents -> Multiply by 100
                "currency": "BRL",
            },
            "payment_method": {
                "soft_descriptor": self.acquirer_id.company_id.name,
                "type": self.payment_token_id.pagseguro_payment_method,
                "installments": self.payment_token_id.pagseguro_installments,
                "capture": self.acquirer_id.pagseguro_capture,
                "card": {
                    "encrypted": self.payment_token_id.pagseguro_card_token,
                },
            },
        }

    def _get_pagseguro_boleto_charge_params(self):
        """
        Returns pagseguro boleto charge params.
        """
        partner = self.payment_token_id.partner_id
        # Boleto expires in 3 days
        due_date = datetime.datetime.now() + datetime.timedelta(days=3)

        if self.acquirer_id.pagseguro_notification_url:
            notification_url = self.acquirer_id.pagseguro_notification_url
        else:
            base_url = self.env["ir.config_parameter"].get_param("web.base.url")
            notification_url = base_url + "/notification-url"

        CHARGE_PARAMS = {
            "reference_id": self.display_name,
            "description": self.display_name,
            "amount": {
                "value": int(self.amount * 100),
                "currency": "BRL",
            },
            "notification_urls": [notification_url],
            "payment_method": {
                "soft_descriptor": self.acquirer_id.company_id.name,
                "type": "BOLETO",
                "boleto": {
                    "due_date": fields.Date.to_string(due_date),
                    "instruction_lines": {
                        "line_1": "Pagamento processado para DESC Fatura",
                        "line_2": "Via PagSeguro",
                    },
                    "holder": {
                        "name": partner.name,
                        "tax_id": punctuation_rm(partner.cnpj_cpf),
                        "email": partner.email,
                        "address": {
                            "street": partner.street_name,
                            "number": partner.street_number,
                            "locality": partner.district,
                            "city": partner.city_id.name,
                            "region": partner.state_id.name,
                            "region_code": partner.state_id.code,
                            "country": partner.country_id.name,
                            "postal_code": punctuation_rm(partner.zip),
                        },
                    },
                },
            },
        }

        return CHARGE_PARAMS

    @api.multi
    def _get_pagseguro_charge_params(self):
        """Returns dict containing the required body information to create a
        charge on Pagseguro."""
        if self.payment_token_id.pagseguro_payment_method == "CREDIT_CARD":
            return self._get_pagseguro_credit_card_charge_params()
        elif self.payment_token_id.pagseguro_payment_method == "BOLETO":
            return self._get_pagseguro_boleto_charge_params()

    def log_transaction(self, reference, message):
        """Logs a transaction. It can be either a successful or a failed one."""
        self.sudo().write(
            {
                "date": fields.datetime.now(),
                "acquirer_reference": reference,
                "state_message": message,
            }
        )

    @staticmethod
    def pprint_filtered_response(response):
        # Returns response removing payment's sensitive information
        output_response = response.copy()
        output_response.pop("links", None)
        output_response.pop("metadata", None)
        output_response.pop("notification_urls", None)
        output_response.pop("payment_method", None)

        return pprint.pformat(output_response)

    @api.multi
    def pagseguro_boleto_do_transaction(self):
        self.ensure_one()
        result = self._create_pagseguro_charge()
        self._pagseguro_s2s_validate_tree(result)
        return result

    @api.multi
    def pagseguro_check_transaction(self):
        if not self.pagseguro_s2s_check_link:
            raise ValidationError(_("There is no check link for this transaction."))

        _logger.info(
            "pagseguro_check_transaction: Sending values to URL %s",
            self.pagseguro_s2s_check_link,
        )

        r = requests.get(
            self.pagseguro_s2s_check_link,
            headers=self.acquirer_id._get_pagseguro_api_headers(),
        )
        res = r.json()

        _logger.info(
            "pagseguro_check_transaction: Transaction %s has status %s"
            % (res["id"], res.get("status"))
        )
        self._set_transaction_state(res)
