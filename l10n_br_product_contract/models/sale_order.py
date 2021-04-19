# Copyright 2021 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _


class SaleOrder(models.Model):

    _inherit = 'sale.order'

    @api.multi
    def _prepare_contract_value(self, contract_template):
        self.ensure_one()
        vals = self._prepare_br_fiscal_dict()
        vals.update(super()._prepare_contract_value(contract_template))
        return vals
