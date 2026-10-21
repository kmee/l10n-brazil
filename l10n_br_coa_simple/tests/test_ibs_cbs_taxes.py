# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_br_coa.tests.common import IbsCbsTaxesMixin


@tagged("post_install", "-at_install")
class TestIbsCbsTaxesSimple(IbsCbsTaxesMixin, TransactionCase):
    """The taxes of the simple chart use its own accounts, by exact code.

    IBS, CBS and IS go to the liability (2.1.4.02.11 to 13) and to the asset
    (1.1.2.05.11 to 13) of the chart. The chart has no revenue deduction for
    them, so the deductible ones use the default account (3.1.1.04.GEN).
    """

    chart_template = "br_oca_simple"
    tax_framework = "1"
    expected_accounts = {
        "tax_template_out_ibs": ("2.1.4.02.11", "1.1.2.05.11"),
        "tax_template_in_ibs": ("1.1.2.05.11", "2.1.4.02.11"),
        "tax_template_out_cbs": ("2.1.4.02.12", "1.1.2.05.12"),
        "tax_template_in_cbs": ("1.1.2.05.12", "2.1.4.02.12"),
        "tax_template_out_ibs_deductible": ("3.1.1.04.GEN", "3.1.1.04.GEN"),
        "tax_template_in_ibs_deductible": ("3.1.1.04.GEN", "2.1.4.02.11"),
        "tax_template_out_cbs_deductible": ("3.1.1.04.GEN", "3.1.1.04.GEN"),
        "tax_template_in_cbs_deductible": ("3.1.1.04.GEN", "2.1.4.02.12"),
        "tax_template_out_is": ("2.1.4.02.13", "1.1.2.05.13"),
        "tax_template_in_is": ("1.1.2.05.13", "2.1.4.02.13"),
        "tax_template_out_is_deductible": ("3.1.1.04.GEN", "3.1.1.04.GEN"),
        "tax_template_in_is_deductible": ("3.1.1.04.GEN", "2.1.4.02.13"),
    }

    def test_no_account_with_a_review_suffix_beside_the_chart_ones(self):
        codes = [
            account.code
            for account in self.env["account.account"]
            .with_company(self.company)
            .search([("company_ids", "in", self.company.id)])
        ]
        for code in codes:
            if code.endswith((".GEN", ".BR")):
                self.assertNotIn(code.rsplit(".", 1)[0], codes, code)
        self.assertFalse([code for code in codes if code.endswith(".BR")])
