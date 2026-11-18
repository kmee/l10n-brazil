# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo.tests.common import tagged

from .common_entrada import SpedEntradaCommon


@tagged("post_install", "-at_install")
class TestRegimeOfTheGroup(SpedEntradaCommon):
    """The PIS/COFINS regime of the tax group has a screen, and a group that
    does not say it follows the company."""

    def _assessment(self, tax_domain):
        group = self.env["account.tax.group"].search(
            [
                (
                    "fiscal_tax_group_id",
                    "=",
                    self.env.ref(f"l10n_br_fiscal.tax_group_{tax_domain}").id,
                )
            ],
            limit=1,
        )
        group.regime = "not_applicable"
        return self.env["l10n_br_tax.assessment"].create(
            {
                "company_id": self.company.id,
                "tax_group_id": group.id,
                "date_from": "2026-07-01",
                "date_to": "2026-07-31",
            }
        )

    def test_the_tax_group_has_a_screen_with_the_regime(self):
        action = self.env.ref("l10n_br_tax_assessment.action_account_tax_group")
        self.assertEqual(action.res_model, "account.tax.group")
        view = self.env.ref("l10n_br_tax_assessment.view_account_tax_group_form")
        self.assertIn('name="regime"', view.arch)
        field = self.env["account.tax.group"]._fields["regime"]
        self.assertEqual(field.string, "Regime de apuração")

    def test_a_company_of_the_presumed_profit_is_cumulative(self):
        for domain in ("pis", "cofins"):
            self.assertEqual(self._assessment(domain).regime, "cumulative", domain)

    def test_a_company_of_the_real_profit_is_non_cumulative(self):
        self.company.profit_calculation = "real"
        for domain in ("pis", "cofins"):
            self.assertEqual(self._assessment(domain).regime, "non_cumulative", domain)

    def test_the_icms_has_no_regime(self):
        self.company.profit_calculation = "real"
        self.assertEqual(self._assessment("icms").regime, "not_applicable")

    def test_the_regime_of_the_group_wins(self):
        assessment = self._assessment("pis")
        assessment.tax_group_id.regime = "non_cumulative"
        self.assertEqual(assessment.regime, "non_cumulative")
