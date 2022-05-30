# Copyright 2019 Akretion (Raphaël Valyi <raphael.valyi@akretion.com>)
# Copyright 2022 KMEE  (Renan Hiroki Bastos <renan.hiroki@kmee.com.br>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class ResCountryState(models.Model):
    _inherit = "res.country.state"
    _nfe_search_keys = ["ibge_code", "code"]
    _nfe_extra_domain = [("ibge_code", "!=", False)]
