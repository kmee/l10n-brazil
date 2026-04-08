# Copyright 2024 - TODAY, Kaynnan Lemes <kaynnan.lemes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models

from odoo.addons.l10n_br_fiscal.constants.fiscal import FISCAL_IN


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        super()._onchange_partner_id()
        if self.fiscal_operation_type == FISCAL_IN:
            for line in self.invoice_line_ids:
                if line.product_id:
                    partner_service_type = (
                        line.partner_id.partner_service_type_ids.filtered(
                            lambda x: x.product_id == line.product_id
                        )
                    )
                    if partner_service_type:
                        line.service_type_id = partner_service_type.service_type_id
                    else:
                        line.service_type_id = line.product_id.service_type_id
