# Copyright 2024 - TODAY, Kaynnan Lemes <kaynnan.lemes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ResPartner(models.Model):
    _inherit = "res.partner"

    # TODO: Add WH fields for State and Country
    wh_cityhall = fields.Boolean(string="Is City Hall?", default=False)

    @api.constrains("city_id", "wh_cityhall")
    def _check_unique_cityhall(self):
        for record in self:
            if record.wh_cityhall:
                existing_count = self.sudo().search_count(
                    [
                        ("city_id", "=", record.city_id.id),
                        ("wh_cityhall", "=", True),
                        ("id", "!=", record.id),
                    ]
                )
                if existing_count > 0:
                    raise ValidationError(
                        _(
                            "Only one partner with the same City Hall can "
                            "exist in the same city."
                        )
                    )
