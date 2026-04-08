# Copyright (C) 2022 Marcel Savegnago - Escodoo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("br_oca_ans")
    def _get_br_oca_ans_template_data(self):
        return {
            "name": _("Plano de Contas ANS - RN 528 04-2022"),
            "parent": "br_oca",
            "visible": True,
            "cash_account_code_prefix": "121119011",
            "bank_account_code_prefix": "121319011",
            "transfer_account_code_prefix": "121219011",
            "property_account_receivable_id": "account_template_ans_12311101101",
            "property_account_payable_id": "account_template_ans_21821901101",
            "property_account_expense_categ_id": "account_template_ans_41111101101",
            "property_account_income_categ_id": "account_template_ans_31111101101",
        }
