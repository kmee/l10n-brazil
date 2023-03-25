# Copyright 2023 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class PosSession(models.Model):

    _inherit = "pos.session"

    def _pos_ui_models_to_load(self):
        result = super()._pos_ui_models_to_load()
        result.append("l10n_br_pos.product_fiscal_map")
        return result

    def _loader_params_l10n_br_pos_product_fiscal_map(self):
        return {
            "search_params": {
                "domain": [
                    ("pos_config_id", "=", self.config_id.id),
                    ("company_id", "=", self.company_id.id),
                ],
                "fields": [],
            }
        }

    def _get_pos_ui_l10n_br_pos_product_fiscal_map(self, params):
        return self.env["l10n_br_pos.product_fiscal_map"].search_read(
            **params["search_params"]
        )

    def _loader_params_product_product(self):
        result = super()._loader_params_product_product()
        result["search_params"]["fields"].extend(
            [
                "tax_icms_or_issqn",
                "fiscal_type",
                "icms_origin",
                "fiscal_genre_code",
                "ncm_id",
                "nbm_id",
                "fiscal_genre_id",
                "service_type_id",
                "city_taxation_code_id",
                "ipi_guideline_class_id",
                "ipi_control_seal_id",
                "nbs_id",
                "cest_id",
            ]
        )
        return result

    def _loader_params_res_company(self):
        result = super()._loader_params_res_company()
        result["search_params"]["fields"].extend(
            [
                "legal_name",
                "cnpj_cpf",
                "inscr_est",
                "inscr_mun",
                "suframa",
                "tax_framework",
                "street_number",
                "city_id",
                "street_name",
                "zip",
                "district",
            ]
        )
        return result
