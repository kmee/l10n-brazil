# Copyright 2023 - TODAY, Escodoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("br_oca_avus")
    def _get_br_oca_avus_template_data(self):
        return {
            "name": _("Plano de Contas Avus"),
            "parent": "br_oca",
            "visible": True,
            "cash_account_code_prefix": "1.1.1.01.",
            "bank_account_code_prefix": "1.1.1.02.",
            "transfer_account_code_prefix": "1.1.1.02.",
            "property_account_receivable_id": "account_template_avus_1_1_2_01_0001",
            "property_account_payable_id": "account_template_avus_2_1_1_01_0001",
            "property_account_expense_categ_id": "account_template_avus_4_1_2_01_0009",
            "property_account_income_categ_id": "account_template_avus_3_1_1_01_0001",
        }
