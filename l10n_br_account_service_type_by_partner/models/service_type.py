# Copyright 2024 - TODAY, Kaynnan Lemes <kaynnan.lemes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ServiceType(models.Model):

    _inherit = "l10n_br_fiscal.service.type"

    can_be_selected_on_partner = fields.Boolean(string="Can be selected on Partner")
