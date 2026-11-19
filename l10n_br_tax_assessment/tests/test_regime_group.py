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

    def test_the_tax_group_screens_of_the_core_have_the_regime(self):
        """The default form of the tax group and the list of the action of the
        core (Accounting > Configuration > Tax Groups) carry the regime, and
        there is no second action or menu for the same model."""
        model = self.env["account.tax.group"]
        self.assertIn('name="regime"', model.get_view(view_type="form")["arch"])
        action = self.env.ref("account.action_tax_group")
        tree = model.get_view(view_id=action.view_id.id, view_type="tree")
        self.assertIn('name="regime"', tree["arch"])
        actions = self.env["ir.actions.act_window"].search(
            [("res_model", "=", "account.tax.group")]
        )
        self.assertEqual(actions, action)
        self.assertEqual(model._fields["regime"].string, "Regime de apuração")

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

    def test_the_fiscal_manager_reaches_the_tax_groups_without_debug_mode(self):
        """The menu of the core for the tax groups needs the developer mode: the
        menu next to the assessment opens the same action to the accounting
        manager."""
        menu = self.env.ref("l10n_br_tax_assessment.menu_tax_group_regime")
        self.assertEqual(menu.action, self.env.ref("account.action_tax_group"))
        user = self.env["res.users"].create(
            {
                "name": "Accounting manager",
                "login": "accounting_manager_tax_group",
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("account.group_account_manager").id,
                        ],
                    )
                ],
            }
        )
        visible = self.env["ir.ui.menu"].with_user(user)._visible_menu_ids(debug=False)
        self.assertIn(menu.id, visible)
