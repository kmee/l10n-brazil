# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import importlib.util

from odoo.modules.module import get_module_path
from odoo.tests import TransactionCase, tagged

NEW_GROUP = "tax_group_is"
NEW_TAXES = [
    "tax_template_out_ibs_deductible",
    "tax_template_in_ibs_deductible",
    "tax_template_out_cbs_deductible",
    "tax_template_in_cbs_deductible",
    "tax_template_out_is",
    "tax_template_in_is",
    "tax_template_out_is_deductible",
    "tax_template_in_is_deductible",
]


def _load_migration():
    path = get_module_path("l10n_br_coa")
    spec = importlib.util.spec_from_file_location(
        "l10n_br_coa_post_migration_18_0_3_4_0",
        f"{path}/migrations/18.0.3.4.0/post-migration.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install")
class TestIbsCbsTaxes(TransactionCase):
    """IBS, CBS and IS come with their deductible taxes and the IS group.

    An operation that uses deductible taxes gives the tax back with a
    deductible account tax. Without the IBS and CBS ones the amount is added
    to the receivable a second time.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {
                "name": "Empresa IBS CBS",
                "country_id": cls.env.ref("base.br").id,
            }
        )
        cls.env.user.company_ids = [(4, cls.company.id)]
        cls.env.user.company_id = cls.company
        cls.env["account.chart.template"].try_loading("br_oca", cls.company)

    def _tax(self, key):
        return self.env.ref(
            f"account.{self.company.id}_{key}", raise_if_not_found=False
        )

    def _tax_repartition(self, tax):
        return tax.invoice_repartition_line_ids.filtered(
            lambda line: line.repartition_type == "tax"
        )

    def test_loaded_chart_has_the_new_taxes(self):
        for key in NEW_TAXES:
            tax = self._tax(key)
            self.assertTrue(tax, f"{key} was not loaded")
            deductible = "deductible" in key
            self.assertEqual(tax.deductible, deductible, key)
            line = self._tax_repartition(tax)
            self.assertEqual(line.factor_percent, -100 if deductible else 100, key)
            self.assertTrue(line.account_id, f"{key} has no account")
        self.assertTrue(self._tax(NEW_GROUP), "the IS tax group was not loaded")
        for key in (
            "tax_template_out_ibs",
            "tax_template_in_ibs",
            "tax_template_out_cbs",
            "tax_template_in_cbs",
        ):
            line = self._tax_repartition(self._tax(key))
            self.assertTrue(line.account_id, f"{key} has no account")

    def _remove_new_taxes(self):
        for key in NEW_TAXES:
            tax = self._tax(key)
            tax.unlink()
        self._tax(NEW_GROUP).unlink()
        self.assertFalse(self._tax(NEW_TAXES[0]))
        self.assertFalse(self._tax(NEW_GROUP))

    def test_migration_adds_the_missing_taxes(self):
        """A database loaded before this version gets the taxes."""
        self._remove_new_taxes()
        other = self.env["account.tax"].search(
            [("company_id", "=", self.company.id), ("name", "=", "ICMS Saída")]
        )
        other_account = self._tax_repartition(other).account_id
        # An account the migration must not rewrite.
        custom = self.env["account.account"].create(
            {
                "name": "Conta do cliente",
                "code": "9.9.9.99",
                "account_type": "liability_current",
                "company_ids": [(4, self.company.id)],
            }
        )
        self._tax_repartition(other).account_id = custom

        _load_migration().migrate(self.env.cr, "18.0.3.3.0")
        self.env.invalidate_all()

        self.test_loaded_chart_has_the_new_taxes()
        self.assertEqual(
            self._tax_repartition(other).account_id,
            custom,
            "the migration rewrote the accounts of a tax that already existed",
        )
        self.assertNotEqual(custom, other_account)

    def test_migration_gives_accounts_to_the_plain_ibs_and_cbs_taxes(self):
        """18.0 shipped the plain IBS and CBS taxes with no account."""
        empty = self._tax("tax_template_out_ibs")
        self._tax_repartition(empty).account_id = False
        refund = empty.refund_repartition_line_ids.filtered(
            lambda line: line.repartition_type == "tax"
        )
        refund.account_id = False
        # A plain tax whose account somebody chose is left alone.
        custom_tax = self._tax("tax_template_out_cbs")
        custom = self.env["account.account"].create(
            {
                "name": "Conta escolhida",
                "code": "9.9.9.98",
                "account_type": "liability_current",
                "company_ids": [(4, self.company.id)],
            }
        )
        self._tax_repartition(custom_tax).account_id = custom

        _load_migration().migrate(self.env.cr, "18.0.3.3.0")
        self.env.invalidate_all()

        self.assertTrue(self._tax_repartition(empty).account_id)
        self.assertEqual(self._tax_repartition(custom_tax).account_id, custom)

    def test_migration_is_idempotent(self):
        before = self.env["account.tax"].search_count(
            [("company_id", "=", self.company.id)]
        )
        _load_migration().migrate(self.env.cr, "18.0.3.3.0")
        after = self.env["account.tax"].search_count(
            [("company_id", "=", self.company.id)]
        )
        self.assertEqual(before, after)

    def test_migration_keeps_the_tax_made_by_hand(self):
        """The deductible tax somebody created is not applied twice."""
        key = "tax_template_out_ibs_deductible"
        generated = self._tax(key)
        name = generated.name
        group = generated.tax_group_id
        generated.unlink()
        by_hand = self.env["account.tax"].create(
            {
                "name": name,
                "company_id": self.company.id,
                "tax_group_id": group.id,
                "type_tax_use": "sale",
                "deductible": True,
                "amount": 0.0,
            }
        )

        _load_migration().migrate(self.env.cr, "18.0.3.3.0")

        taxes = self.env["account.tax"].search(
            [("company_id", "=", self.company.id), ("name", "=", name)]
        )
        self.assertEqual(taxes, by_hand)
        self.assertEqual(self._tax(key), by_hand)
