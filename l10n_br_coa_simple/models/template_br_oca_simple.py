# Copyright (C) KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import _, models

from odoo.addons.account.models.chart_template import template


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    @template("br_oca_simple")
    def _get_br_oca_simple_template_data(self):
        return {
            "name": _("Plano de Contas Simplificado"),
            "parent": "br_oca",
            "visible": True,
            "property_account_receivable_id": "coa_simple_11201",
            "property_account_payable_id": "coa_simple_21101",
            "property_account_expense_categ_id": "coa_simple_32103",
            "property_account_income_categ_id": "coa_simple_31101",
        }

    @template("br_oca_simple", "res.company")
    def _get_br_oca_simple_res_company(self):
        return {
            self.env.company.id: {
                "account_default_pos_receivable_account_id": "coa_simple_11203",
                "anglo_saxon_accounting": True,
            },
        }

    def _get_tax_group_accounts(self, template_code):
        """
        Default invoice/refund accounts by tax group

        [tax_group_id xmlid (pseudo)]: {
            ded_account_id: xmlid
            ded_refund_account_id: xmlid
            account_id: xmlid
            refund_account_id: xmlid
        }
        """
        if template_code != "br_oca_simple":
            return super()._get_tax_group_accounts(template_code)

        return {
            "tax_group_icms": {
                "account_id": "coa_simple_21302",
                "refund_account_id": "coa_simple_11402",
                "ded_account_id": "coa_simple_31104",
                "ded_refund_account_id": "coa_simple_31104",
            },
            "tax_group_ipi": {
                "account_id": "coa_simple_21304",
                "refund_account_id": "coa_simple_11402",
                "ded_account_id": "coa_simple_31104",
                "ded_refund_account_id": "coa_simple_31104",
            },
            "tax_group_pis": {
                "account_id": "coa_simple_21305",
                "refund_account_id": "coa_simple_11402",
                "ded_account_id": "coa_simple_31104",
                "ded_refund_account_id": "coa_simple_31104",
            },
            "tax_group_cofins": {
                "account_id": "coa_simple_21306",
                "refund_account_id": "coa_simple_11402",
                "ded_account_id": "coa_simple_31104",
                "ded_refund_account_id": "coa_simple_31104",
            },
            "tax_group_issqn": {
                "account_id": "coa_simple_21303",
                "refund_account_id": "coa_simple_11402",
                "ded_account_id": "coa_simple_31104",
                "ded_refund_account_id": "coa_simple_31104",
            },
            "tax_group_csll": {
                "account_id": "coa_simple_21301",
                "refund_account_id": "coa_simple_11402",
                "ded_account_id": False,
                "ded_refund_account_id": False,
            },
            "tax_group_irpj": {
                "account_id": "coa_simple_21301",
                "refund_account_id": "coa_simple_11402",
                "ded_account_id": False,
                "ded_refund_account_id": False,
            },
            "tax_group_ibs": {
                "account_id": "coa_simple_21307",
                "refund_account_id": "coa_simple_11402",
                "ded_account_id": "coa_simple_31104",
                "ded_refund_account_id": "coa_simple_31104",
            },
            "tax_group_cbs": {
                "account_id": "coa_simple_21308",
                "refund_account_id": "coa_simple_11402",
                "ded_account_id": "coa_simple_31104",
                "ded_refund_account_id": "coa_simple_31104",
            },
            "tax_group_is": {
                "account_id": "coa_simple_21309",
                "refund_account_id": "coa_simple_11402",
                "ded_account_id": "coa_simple_31104",
                "ded_refund_account_id": "coa_simple_31104",
            },
            "tax_group_icmssn": {
                "account_id": "coa_simple_21302",
                "refund_account_id": "coa_simple_11402",
                "ded_account_id": "coa_simple_31104",
                "ded_refund_account_id": "coa_simple_31104",
            },
        }
