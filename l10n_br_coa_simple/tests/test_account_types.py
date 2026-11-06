# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import importlib.util

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

MIGRATION = "18.0.2.2.0"
LOGGER_NAME = "l10n_br_coa_simple_post_migration_18_0_2_2_0"

ASSET = (
    "asset_receivable",
    "asset_cash",
    "asset_current",
    "asset_non_current",
    "asset_prepayments",
    "asset_fixed",
)
LIABILITY = (
    "liability_payable",
    "liability_credit_card",
    "liability_current",
    "liability_non_current",
)
EQUITY = ("equity", "equity_unaffected")
RESULT = (
    "income",
    "income_other",
    "expense",
    "expense_depreciation",
    "expense_direct_cost",
)
# The advance of a customer is a liability, kept as a receivable so that the
# advance is reconciled with the invoice of the customer.
RECEIVABLE_IN_LIABILITIES = ("2.1.2.02.02",)


def load_migration():
    """Import the migration script by path (its folder is a version number)."""
    path = get_module_path("l10n_br_coa_simple")
    spec = importlib.util.spec_from_file_location(
        LOGGER_NAME, f"{path}/migrations/{MIGRATION}/post-migration.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install")
class TestAccountTypes(TransactionCase):
    """The type of every account follows the group it lives in.

    The reports of the localization select by classification and do not
    notice a wrong type; the balance sheet of the core, the year end closing
    and the reconciliation go by the type.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        vals = {
            "name": "Empresa Tipos de Conta",
            "country_id": cls.env.ref("base.br").id,
            "currency_id": cls.env.ref("base.BRL").id,
        }
        if "tax_framework" in cls.env["res.company"]._fields:
            vals["tax_framework"] = "1"
        cls.company = cls.env["res.company"].create(vals)
        cls.env.user.company_ids |= cls.company
        cls.env["account.chart.template"].try_loading(
            "br_oca_simple", cls.company, install_demo=False
        )

    def _accounts(self):
        return (
            self.env["account.account"]
            .with_company(self.company)
            .search([("company_ids", "in", self.company.id)])
        )

    def _account(self, code):
        account = self._accounts().filtered(lambda a: a.code == code)
        self.assertEqual(len(account), 1, code)
        return account

    def test_types_follow_the_group(self):
        for account in self._accounts():
            code, account_type = account.code, account.account_type
            if code.startswith("1."):
                self.assertIn(account_type, ASSET, code)
            elif code in RECEIVABLE_IN_LIABILITIES:
                self.assertEqual(account_type, "asset_receivable", code)
            elif code.startswith(("2.1.", "2.2.")):
                self.assertIn(account_type, LIABILITY, code)
            elif code.startswith(("2.3.", "2.8.")):
                self.assertIn(account_type, EQUITY, code)
            elif code.startswith("3."):
                self.assertIn(account_type, RESULT, code)

    def test_prepaid_expenses_are_prepayments(self):
        prepaid = self._accounts().filtered(lambda a: a.code.startswith("1.1.4."))
        self.assertEqual(len(prepaid), 3)
        for account in prepaid:
            self.assertEqual(account.account_type, "asset_prepayments", account.code)
            self.assertFalse(account.reconcile, account.code)
        # the orphan 1.1.6.01.99 of the official annex lives in the group that exists
        self.assertFalse(
            self._accounts().filtered(lambda a: a.code.startswith("1.1.6"))
        )

    def test_accumulated_depreciation_is_a_fixed_asset(self):
        contra = self._accounts().filtered(
            lambda a: a.code.startswith(("1.2.3.02.", "1.2.4.02."))
            or a.code == "1.2.3.01.71"
        )
        self.assertEqual(len(contra), 9)
        for account in contra:
            self.assertEqual(account.account_type, "asset_fixed", account.code)
        for code in ("1.2.3.02.40", "1.2.3.02.50", "1.2.3.02.51"):
            self._account(code)

    def test_migration_retypes_the_loaded_accounts(self):
        """A company loaded before gets the types, names and code of the CSV."""
        rent = self._account("1.1.4.01.01")
        rent.write(
            {
                "name": "Aluguéis e Arredamentos Pagos Antecipadamente",
                "account_type": "liability_payable",
                "reconcile": True,
            }
        )
        depreciation = self._account("1.2.3.02.20")
        depreciation.write({"account_type": "expense_depreciation"})
        irpj = self._account("3.8.1.01.01")
        irpj.write({"account_type": "equity"})
        other = self._account("1.1.4.01.99")
        other.write({"code": "1.1.6.01.99"})
        # an account renamed by hand keeps its name
        meal = self._account("3.3.2.01.07")
        meal.write({"name": "Refeitório"})

        load_migration().migrate_companies(self.env)
        self.env.invalidate_all()

        self.assertEqual(rent.name, "Aluguéis e Arrendamentos Pagos Antecipadamente")
        self.assertEqual(rent.account_type, "asset_prepayments")
        self.assertFalse(rent.reconcile)
        self.assertEqual(depreciation.account_type, "asset_fixed")
        self.assertEqual(irpj.account_type, "expense")
        self.assertEqual(other.code, "1.1.4.01.99")
        self.assertEqual(meal.name, "Refeitório")

        # idempotent
        snapshot = {a.id: (a.code, a.name, a.account_type) for a in self._accounts()}
        load_migration().migrate_companies(self.env)
        self.env.invalidate_all()
        self.assertEqual(
            {a.id: (a.code, a.name, a.account_type) for a in self._accounts()},
            snapshot,
        )
