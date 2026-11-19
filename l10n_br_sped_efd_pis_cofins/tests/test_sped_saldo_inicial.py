# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

import base64
from datetime import date

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests.common import tagged

from odoo.addons.l10n_br_tax_assessment.tests.common_entrada import SpedEntradaCommon

from .test_sped_credito import CreditMixin

OPENING = "l10n_br_pis_cofins.credit.opening"


@tagged("post_install", "-at_install")
class TestCreditOpening(SpedEntradaCommon):
    """The opening balance of the PIS/COFINS credit of a company that comes from
    another system."""

    profit_calculation = "real"

    def _opening(self, **vals):
        values = {
            "company_id": self.company.id,
            "tax_domain": "pis",
            "cutoff_date": date(2026, 7, 1),
            "origin_period": date(2026, 5, 1),
            "cod_cred": "101",
            "amount": 100.0,
            "used_before": 30.0,
        }
        values.update(vals)
        return self.env[OPENING].create(values)

    def test_the_balance_is_the_credit_less_what_was_used(self):
        opening = self._opening()
        self.assertEqual(opening.balance, 70.0)
        opening.used_before = 100.0
        self.assertEqual(opening.balance, 0.0)

    def test_the_used_credit_cannot_be_above_the_credit(self):
        with self.assertRaises(ValidationError):
            self._opening(used_before=120.0)

    def test_the_origin_is_before_the_first_period_of_the_system(self):
        with self.assertRaises(ValidationError):
            self._opening(origin_period=date(2026, 7, 1))

    def test_the_periods_are_the_first_day_of_the_month(self):
        with self.assertRaises(ValidationError):
            self._opening(origin_period=date(2026, 5, 15))

    def test_a_transferred_credit_needs_the_cnpj_of_the_assignor(self):
        with self.assertRaises(ValidationError):
            self._opening(orig_cred="02")
        self._opening(orig_cred="02", cnpj_suc="11222333000181")

    def test_the_accounting_manager_reaches_the_menu_and_the_fiscal_user_only_reads(
        self,
    ):
        menu = self.env.ref("l10n_br_sped_efd_pis_cofins.menu_credit_opening")
        manager = self.env["res.users"].create(
            {
                "name": "Accounting manager",
                "login": "accounting_manager_credit_opening",
                "company_id": self.company.id,
                "company_ids": [(6, 0, self.company.ids)],
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
        visible = (
            self.env["ir.ui.menu"].with_user(manager)._visible_menu_ids(debug=False)
        )
        self.assertIn(menu.id, visible)
        opening = self._opening()
        reader = self.env["res.users"].create(
            {
                "name": "Fiscal user",
                "login": "fiscal_user_credit_opening",
                "company_id": self.company.id,
                "company_ids": [(6, 0, self.company.ids)],
                "groups_id": [
                    (
                        6,
                        0,
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("l10n_br_fiscal.group_user").id,
                        ],
                    )
                ],
            }
        )
        opening.with_user(reader).read(["balance"])
        with self.assertRaises(AccessError):
            opening.with_user(reader).write({"amount": 200.0})


@tagged("post_install", "-at_install")
class TestCreditOpeningImport(SpedEntradaCommon):
    """The opening balance read from the last EFD Contribuicoes of the previous
    system (registers 1100 and 1500)."""

    profit_calculation = "real"

    FILE = (
        "|0000|006|0|||01062026|30062026|Empresa|11222333000181|SP|3550308||00|0|\n"
        "|1001|0|\n"
        "|1100|042026|01||101|40,00||40,00|10,00|||30,00|5,00|||||25,00|\n"
        "|1100|052026|01||101|20,00||20,00|0|||20,00|20,00|||||0|\n"
        "|1500|042026|01||101|200,00||200,00|50,00|||150,00|0|||||150,00|\n"
        "|1990|3|\n"
    )

    def _import(self, text):
        wizard = self.env["l10n_br_pis_cofins.credit.opening.import"].create(
            {
                "company_id": self.company.id,
                "file": base64.b64encode(text.encode("latin-1")),
                "filename": "efd.txt",
            }
        )
        return wizard.action_import()

    def test_the_balance_of_the_1100_and_the_1500_becomes_the_opening_balance(self):
        action = self._import(self.FILE)
        records = self.env[OPENING].search(action["domain"])
        self.assertEqual(len(records), 2, "the layer that was used up is left out")
        by_key = {(rec.tax_domain, rec.origin_period): rec for rec in records}
        pis_april = by_key[("pis", date(2026, 4, 1))]
        self.assertEqual(pis_april.amount, 40.0)
        self.assertEqual(pis_april.balance, 25.0)
        self.assertEqual(pis_april.used_before, 15.0)
        self.assertEqual(pis_april.cutoff_date, date(2026, 7, 1))
        self.assertEqual(by_key[("cofins", date(2026, 4, 1))].balance, 150.0)

    def test_a_file_that_is_not_an_efd_contribuicoes_is_refused(self):
        with self.assertRaises(UserError):
            self._import("|9999|1|\n")
