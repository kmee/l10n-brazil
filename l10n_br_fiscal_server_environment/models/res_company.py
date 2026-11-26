# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class ResCompany(models.Model):
    _name = "res.company"
    _inherit = ["res.company", "server.env.mixin"]

    @property
    def _server_env_fields(self):
        env_fields = {
            "nfe_environment": {},
            "nfse_environment": {},
        }
        env_fields.update(super()._server_env_fields)
        return env_fields
