# Copyright 2024 - TODAY, Kaynnan Lemes <kaynnan.lemes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models

from odoo.addons.l10n_br_fiscal.constants.fiscal import FISCAL_IN


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    @api.onchange("product_id")
    def _onchange_product_id_fiscal(self):
        super()._onchange_product_id_fiscal()
        if self.product_id and self.move_id.fiscal_operation_type == FISCAL_IN:
            partner_service_type = self.partner_id.partner_service_type_ids.filtered(
                lambda x: x.product_id == self.product_id
            )
            if partner_service_type:
                self.service_type_id = partner_service_type.service_type_id
            else:
                self.service_type_id = self.product_id.service_type_id
