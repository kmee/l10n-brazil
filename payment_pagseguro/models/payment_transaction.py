# Copyright 2020 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import datetime
import logging
import pprint
import re
import json
import requests
from datetime import timedelta
from xml.etree import ElementTree

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)
try:
    from erpbrasil.base.misc import punctuation_rm
except ImportError:
    _logger.error("Biblioteca erpbrasil.base não instalada")

try:
    from pycep_correios import WebService, get_address_from_cep
except ImportError:
    _logger.warning("Library PyCEP-Correios not installed !")

URL_VIACEP = "http://www.viacep.com.br/ws/90050003/json"


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

    pagseguro_boleto_due_date = fields.Date(string="Pagseguro boleto due date")

    def _set_transaction_state(self, res):
        """Change transaction state based on Pagseguro status"""
        pagseguro_status = ''
        if res.get("charges"):
            pagseguro_charge = res.get("charges") and res.get("charges")[0]
            pagseguro_status = pagseguro_charge.get("status")
        elif res.get("qr_codes"):
            pagseguro_status = "AUTHORIZED"
        else:
            pagseguro_status = res.get("status")

        if pagseguro_status == "PAID":
            self._set_transaction_done()
        elif pagseguro_status in ["AUTHORIZED", "WAITING", "IN_ANALYSIS"]:
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

    def _create_pagseguro_order(self):
        """Creates the s2s payment.

        Uses encrypted credit card.
        """
        api_url_charge = "https://%s/orders" % (
            self.acquirer_id._get_pagseguro_api_url()
        )

        self.payment_token_id.active = False

        _logger.info(
            "_create_pagseguro_order: Sending values to URL %s", api_url_charge
        )
        json_param = self._get_pagseguro_order_params()
        r = requests.post(
            api_url_charge,
            json=json_param,
            headers=self.acquirer_id._get_pagseguro_api_headers(),
        )
        res = r.json()
        _logger.info(
            "_create_pagseguro_order: Values received:\n%s",
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
        result = self._create_pagseguro_order()

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
        if not self.pagseguro_s2s_capture_link:
            raise ValidationError(
                _("Please check the transaction capture link")
            )

        _logger.info(
            "pagseguro_s2s_capture_transaction: Sending values to URL %s",
            self.pagseguro_s2s_capture_link,
        )
        r = requests.post(
            self.pagseguro_s2s_capture_link,
            headers=self.acquirer_id._get_pagseguro_api_headers(),
            json=self._get_pagseguro_capture_params(),
        )
        res = r.json()
        _logger.info(
            "pagseguro_s2s_capture_transaction: Values received:\n%s",
            self.pprint_filtered_response(res),
        )
        # TODO: verificar se estrutura do retorno do endpoint orders é igual ao do endpoint charges e adaptar
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
                message=res["error_messages"][0]["description"],
            )

    @api.multi
    def pagseguro_s2s_void_transaction(self):
        """Voids an authorized transaction."""
        # TODO: verificar mudanças e refatorar
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

        if tree.get("error_messages"):
            for error_message in tree.get('error_messages', []):
            # TODO: Tratar erro
                _logger.error("Erro na transação:\ncodigo: %s\ndescricao: %s" % (error_message.get('code'), error_message.get('description')))
            return False

        # TODO: refatorar para adaptar ao schema de retorno do endpoint /orders
        payment = tree.get("charges", False) and tree.get("charges", {})[0].get("payment_response")
        if payment:
            code = payment.get("code")
            if code == "20000":
                self.log_transaction(reference=tree.get("id"), message="")

            # store capture and void links for future manual operations
            self.store_links(tree)
            self.pagseguro_boleto_due_date = self._get_boleto_due_date(tree)
            self._set_transaction_state(tree)
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

    def _get_boleto_due_date(self, tree):
        charges = tree.get('charges')
        for charge in charges:
            payment_method = charge.get('payment_method')
            if payment_method:
                boleto = payment_method.get("boleto")
                if boleto:
                    return boleto.get('due_date', False)
        return False

    def _store_links_credit(self, tree):

        for link in tree.get("charges", {})[0].get("links"):
            if link.get("rel") == "SELF":
                self.pagseguro_s2s_check_link = link.get("href")
            if link.get("rel") == "CHARGE.CAPTURE":
                self.pagseguro_s2s_capture_link = link.get("href")
            if link.get("rel") == "CHARGE.CANCEL":
                self.pagseguro_s2s_void_link = link.get("href")

    def _store_links_boleto(self, tree):
        for link in tree.get("charges", {})[0].get("links"):
            if link.get("media") == "application/json":
                self.pagseguro_s2s_check_link = link.get("href")
            elif link.get("media") == "application/pdf":
                self.pagseguro_boleto_pdf_link = link.get("href")
            elif link.get("media") == "image/png":
                self.pagseguro_boleto_image_link = link.get("href")

    def _store_data_credit(self, tree):
        for charge in tree.get("charges", {}):
            if charge.get("payment_method", {}).get("type") == "CREDIT_CARD":
                self.payment_token_id.pagseguro_installments = charge.get('payment_method').get('installments')
                card = charge["payment_method"].get('card')
                self.payment_token_id.pagseguro_card_brand = card.get('brand')
                self.payment_token_id.pagseguro_card_last_digits = card.get('last_digits')
                self.payment_token_id.pagseguro_card_holder_name = card.get('holder', {}).get('name')

    def _save_barcode(self, tree):
        barcode = tree.get("charges") and \
                  tree.get("charges")[0].get("payment_method", {}).get("boleto", {}).get("barcode")
        self.pagseguro_boleto_barcode = barcode

    def store_links(self, tree):
        if self.payment_token_id.pagseguro_payment_method == "CREDIT_CARD":
            self._store_links_credit(tree)
            self._store_data_credit(tree)
        elif self.payment_token_id.pagseguro_payment_method == "BOLETO":
            self._store_links_boleto(tree)
            self._save_barcode(tree)

    @api.multi
    def _validate_tree_message(self, tree):
        # TODO: verificar essa função
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

    def _get_pagseguro_capture_params(self):
        return {
            'amount': {
                  'value': int(self.amount * 100)
            }
        }

    def _get_notification_url(self):
        if self.acquirer_id.pagseguro_notification_url:
            notification_url = self.acquirer_id.pagseguro_notification_url
        else:
            base_url = self.env["ir.config_parameter"].get_param("web.base.url")
            notification_url = base_url + "/notification-url"

        return notification_url

    @api.multi
    def _get_pagseguro_credit_card_charge_params(self):
        """
        Returns pagseguro credit card charge params.
        """
        return {
            "reference_id": str(self.display_name[:13]),
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
            "notification_urls": [self._get_notification_url()]
        }

    def _get_pagseguro_boleto_charge_params(self):
        """
        Returns pagseguro boleto charge params.
        """
        partner = self.payment_token_id.partner_id
        # Boleto expires in 3 days if the value of pagseguro_boleto_due_date_in_days is empty, to prevent errors
        due_date_in_days = self.acquirer_id.pagseguro_boleto_due_date_in_days or 3
        due_date = fields.Datetime.now() + timedelta(days=due_date_in_days)

        CHARGE_PARAMS = {
            "reference_id": self.display_name,
            "description": self.display_name,
            "amount": {
                "value": int(self.amount * 100),
                "currency": "BRL",
            },
            "notification_urls": [self._get_notification_url()],
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
    def _get_pagseguro_items_params(self):
        items = []
        for line in self.sale_order_ids[0].order_line:
            item = {
                "reference_id": line.product_id.default_code,
                "name": line.product_id.name,
                "quantity": int(line.product_uom_qty),
                "unit_amount": int(line.price_unit * 100),
            }
            items.append(item)
        return items

    @api.multi
    def _get_phone_params(self):
        phone = self.check_br_phone_number(self.partner_id)
        return [
                    {
                        "country": "55",
                        "area": phone['ddd'],
                        "number": phone['number'],
                        "type": phone['type'],
                    }
                ]

    def check_br_phone_number(self, partner):
        """ Verifica se o número do cliente é valido.
            Retorna em formato de dicionario o número completo sem pontuação, DDI, DDD, o número do cliente.
            Caso o número não tenha DDD, é realizada uma busca do DDD a partir do CEP do cliente.
        """
        phone_number = partner.phone
        cep = partner.zip
        if not phone_number or not cep:
            raise ValidationError("O Número de telefone ou CEP do cliente não foram preenchidos!")
        else:
            regex_check_phone = re.compile(r"(?P<full_number>"
                                           r"(?P<ddi>\+?55\s?)?"
                                           r"(?P<ddd>\(?\d{2}\)?\s?\-?\.?)"
                                           r"?(?P<number>\d{4,5}\-?\.?\s?\d{4})"
                                           r")")
            valid_phone_number = regex_check_phone.match(phone_number)
            if not valid_phone_number:
                raise ValidationError("O número de telefone não é válido!")
            else:
                full_number = re.sub(r'\W', '', valid_phone_number['full_number'] or '')
                ddi = re.sub(r'\W', '', valid_phone_number['ddi'] or '')
                ddd = re.sub(r'\W', '', valid_phone_number['ddd'] or '')
                number = re.sub(r'\W', '', valid_phone_number['number'] or '')

                regex_repeated_numbers = re.compile(r"((\S)\2{5,})")
                check_repeated_numbers = number if len(number) == 8 else number[1:]
                if regex_repeated_numbers.match(check_repeated_numbers):
                    raise ValidationError("O número de telefone não é válido")

                if not ddd:
                    ddd = self.get_ddd_from_cep(cep)

                return {
                    'full_number': full_number,
                    'ddi': ddi,
                    'ddd': ddd,
                    'number': number,
                    'type': 'HOME' if len(number) == 8 else 'MOBILE'
                }

    @staticmethod
    def get_ddd_from_cep(cep):
        """Retorna o DDD a partir do CEP do cliente."""
        cep_str = punctuation_rm(cep)
        try:
            response = requests.get(URL_VIACEP.format(cep_str))
            if not response.status_code == 200:
                raise ValidationError("Telefone do cliente sem DDD!")
            else:
                address = json.loads(response.text)
                if address.get("erro"):
                    raise ValidationError("DDD do cliente não encontrado!")
                return address.get("ddd")
        except Exception as e:
            raise UserError(f"Erro no PyCEP-Correios: {str(e)}")

    @api.multi
    def _get_pagseguro_order_params(self):
        """Returns dict containing the required body information to create a
        charge on Pagseguro."""

        ORDER_PARAMS = {
            "reference_id": self.sale_order_ids[0].name,
            "customer": {
                "name": self.partner_name,
                "email": self.partner_email,
                "tax_id": punctuation_rm(self.partner_id.vat)
                or punctuation_rm(self.partner_id.cnpj_cpf),
                "phones": self._get_phone_params(),
            },
            "items": self._get_pagseguro_items_params(),
            "notification_urls": [self._get_notification_url()],
            "qr_codes": [{"amount": {"value": int(self.amount * 100)}}],
            "shipping": {
                "address": {
                    "street": self.partner_id.street,
                    "number": self.partner_id.street_number or "S/N",
                    "complement": self.partner_id.street2 or "N/A",
                    "locality": self.partner_id.district,
                    "city": self.partner_id.city_id.name,
                    "region_code": self.partner_id.state_id.code,
                    "country": "BRA",
                    "postal_code": punctuation_rm(self.partner_zip),
                }
            },

        }
        charges = self._get_pagseguro_charge_params()
        if charges:
            ORDER_PARAMS.update({'charges': charges})
        else:
            # enviar cobrança via pix/qr_code
            import pytz
            expiration = str(
                (
                    datetime.datetime.now(pytz.timezone('America/Sao_Paulo')) +
                    datetime.timedelta(days=1)
                ).replace(microsecond=0).isoformat()
            )
            ORDER_PARAMS['qr_codes'][0].update({'expiration_date': expiration})

        return ORDER_PARAMS

    def _get_pagseguro_charge_params(self):
        charges = []
        if self.payment_token_id.pagseguro_payment_method == "CREDIT_CARD":
            charges.append(self._get_pagseguro_credit_card_charge_params())
        elif self.payment_token_id.pagseguro_payment_method == "BOLETO":
            charges.append(self._get_pagseguro_boleto_charge_params())
        elif self.payment_token_id.pagseguro_payment_method == "PIX":
            pass
        return charges

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
        # output_response.pop("links", None)
        # output_response.pop("metadata", None)
        # output_response.pop("notification_urls", None)
        # output_response.pop("payment_method", None)

        return pprint.pformat(output_response)

    @api.multi
    def pagseguro_boleto_do_transaction(self):
        self.ensure_one()
        result = self._create_pagseguro_order()
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

        _logger.info(str(res))
        _logger.info(
            "pagseguro_check_transaction: Transaction %s has status %s"
            % (res.get("id"), res.get("status"))
        )
        self._pagseguro_s2s_validate_tree(res)
        self._set_transaction_state(res)
