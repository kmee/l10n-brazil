# Copyright (C) 2014  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import fields, models
from odoo.addons.l10n_br_fiscal.constants.fiscal import FINAL_CUSTOMER_YES


class Company(models.Model):
    _inherit = 'res.company'

    sale_fiscal_operation_id = fields.Many2one(
        comodel_name='l10n_br_fiscal.operation',
        string='Operação Fiscal Padrão de Vendas',
    )

    sale_final_consumption_fiscal_operation_id = fields.Many2one(
        comodel_name='l10n_br_fiscal.operation',
        string='Operação Fiscal Padrão de Vendas para Consumo Final',
        domain=[('ind_final', '=', FINAL_CUSTOMER_YES)],
    )

    copy_note = fields.Boolean(
        string='Copy Sale note on invoice',
        default=False,
    )
