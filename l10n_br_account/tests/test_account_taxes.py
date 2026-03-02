# Copyright (C) 2020  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo.tests.common import tagged

from .common import AccountMoveBRCommon


@tagged("post_install", "-at_install")
class TestAccountTaxes(AccountMoveBRCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # load_fiscal_taxes() creates account.tax.group records with
        # fiscal_tax_group_id linking them to l10n_br_fiscal.tax.group,
        # plus the corresponding account.tax records. The base
        # AccountMoveBRCommon.setUpClass doesn't call it, so we do it here.
        cls.env["account.chart.template"].load_fiscal_taxes(
            companies=[cls.company_data["company"]]
        )

    def test_account_taxes(self):
        """Test if account taxes are related with fiscal taxes.

        load_fiscal_taxes() creates account.tax records whose tax groups
        are linked to l10n_br_fiscal.tax.group via fiscal_tax_group_id.
        This test verifies that relationship exists for the test company.
        """
        company = self.company_data["company"]
        account_tax_groups = self.env["account.tax.group"].search(
            [
                ("fiscal_tax_group_id", "!=", False),
                ("company_id", "=", company.id),
            ]
        )
        self.assertTrue(
            account_tax_groups,
            "No account tax groups with fiscal_tax_group_id found for "
            f"company {company.name}. load_fiscal_taxes() may not have "
            "been called during setup.",
        )

        # Verify we have account.tax records in these groups
        account_taxes = self.env["account.tax"].search(
            [
                ("tax_group_id", "in", account_tax_groups.ids),
                ("company_id", "=", company.id),
            ]
        )
        self.assertTrue(
            account_taxes,
            "No account taxes found in fiscal tax groups.",
        )
