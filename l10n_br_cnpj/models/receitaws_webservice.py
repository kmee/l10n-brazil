# Copyright 2022 KMEE - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, models
from odoo.exceptions import ValidationError

RECEITAWS_URL = "https://www.receitaws.com.br/v1/cnpj/"


class ReceitawsWebservice(models.Model):
    _inherit = "l10n_br_cnpj.webservice"

    @staticmethod
    def receitaws_get_api_url(cnpj):
        return RECEITAWS_URL + cnpj

    @staticmethod
    def receitaws_get_headers():
        return {}

    def receitaws_validate(self, response):
        self._validate(response)
        data = response.json()
        if data.get("status") == "ERROR":
            raise ValidationError(_(data.get("message")))

        return data

    def receitaws_import_data(self, data):
        legal_name = self.get_data(data, "nome", title=True)
        fantasy_name = self.get_data(data, "fantasia", title=True)
        phone, mobile = self.receitaws_get_phones(data)
        state_id, city_id = self.get_state_city(data)
        capital_social = self.get_data(data, "capital_social")
        cnae_id = self.receitaws_get_cnae(data)

        res = {
            "legal_name": legal_name,
            "name": fantasy_name if fantasy_name else legal_name,
            "email": self.get_data(data, "email", lower=True),
            "street_name": self.get_data(data, "logradouro", title=True),
            "street2": self.get_data(data, "complemento", title=True),
            "district": self.get_data(data, "bairro", title=True),
            "street_number": self.get_data(data, "numero"),
            "zip": self.get_data(data, "cep"),
            "phone": phone,
            "mobile": mobile,
            "state_id": state_id,
            "city_id": city_id,
            "capital_social": capital_social,
            "cnae_main_id": cnae_id,
        }

        return res

    @staticmethod
    def receitaws_get_phones(data):
        """Get phones from data.
        If there is more than one phone, the second is assigned to mobile."""
        phone = False
        mobile = False
        if data.get("telefone") != "":
            phones = data["telefone"].split("/")
            phone = phones[0]
            if len(phones) > 1:
                mobile = phones[1][1:]  # Remove Empty space separation

        return [phone, mobile]

    def get_state_city(self, data):
        state_id = False
        city_id = False
        if data.get("uf") != "":
            state = self.env["res.country.state"].search(
                [
                    ("code", "=", data["uf"]),
                    ("country_id.code", "=", "BR"),
                ],
                limit=1,
            )
            if state.id:
                state_id = state.id

            if data.get("municipio") != "":
                city = self.env["res.city"].search(
                    [
                        ("name", "=ilike", data["municipio"].title()),
                        ("state_id.id", "=", state_id),
                    ]
                )
                if len(city) == 1:
                    city_id = city.id

        return [state_id, city_id]

    def receitaws_get_cnae(self, data):
        cnae_main = data.get("atividade_principal")[0]
        cnae_code = self.get_data(cnae_main, "code")

        return self._get_cnae(cnae_code)
