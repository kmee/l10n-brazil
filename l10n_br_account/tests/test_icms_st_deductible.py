# Copyright 2026 KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import importlib.util

from odoo.modules.module import get_module_path
from odoo.tests import tagged

from .common import AccountMoveBRCommon

ST_SALE = "tax_template_out_icms_subist"
ST_DEDUCTIBLE = "tax_template_icms_st_out_deductible"
# Tax -> (invoice account, refund account), without the review suffix. The
# codes are the ones of l10n_br_coa_generic.
EXPECTED_ACCOUNTS = {
    ST_SALE: ("2.1.7.1.11", "2.1.7.1.11"),
    ST_DEDUCTIBLE: ("6.1.1.2.07", "6.1.1.2.27"),
}


def load_migration():
    """The migration script of `l10n_br_coa` 18.0.3.5.0, loaded by path.

    The folder is named after the version and the file has a dash: neither is
    a valid module name. It is the same file Odoo runs on `-u`.
    """
    path = get_module_path("l10n_br_coa")
    spec = importlib.util.spec_from_file_location(
        "l10n_br_coa_post_migration_18_0_3_5_0",
        f"{path}/migrations/18.0.3.5.0/post-migration.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install")
class TestIcmsStDeductible(AccountMoveBRCommon):
    """The ICMS ST of a sale must not be added twice to the receivable.

    With deductible taxes the product line takes the full document total, ST
    included, and the deductible account tax gives each tax back with a
    negative factor. Without the deductible ICMS ST the ST tax line adds the
    ST once more and the title is bigger than the invoice total.

    Sale of 1.000,00 with own ICMS of 20% (200,00) and ICMS ST of 20% with an
    MVA of 50%: ST base 1.500,00, ST 300,00 - 200,00 = 100,00. Invoice total
    and receivable: 1.100,00.
    """

    chart_template = "generic_coa"
    # The core chart has none of the Brazilian codes: `load_fiscal_taxes`
    # creates the tax accounts with the review suffix.
    account_suffix = ".BR"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The complex_tax of the core fixture is not a fiscal tax and falls in
        # a fiscal tax group, unbalancing the entry (see test_ibs_cbs_deductible).
        cls.env["account.tax"].with_context(active_test=False).search(
            [("name", "like", "complex_tax")]
        ).unlink()
        cls.company = cls.company_data["company"]
        cls.env["account.chart.template"].load_fiscal_taxes(companies=[cls.company])
        cls.configure_normal_company_taxes()
        icmsst_20_mva_50 = cls.env["l10n_br_fiscal.tax"].create(
            {
                "name": "ICMS ST 20% MVA 50%",
                "tax_group_id": cls.env.ref("l10n_br_fiscal.tax_group_icmsst").id,
                "tax_base_type": "percent",
                "percent_amount": 20.0,
                "percent_reduction": 0.0,
                "percent_debit_credit": 0.0,
                "value_amount": 0.0,
                "icmsst_value": 0.0,
                "icmsst_base_type": "4",
                "icmsst_mva_percent": 50.0,
                "cst_in_id": cls.env.ref("l10n_br_fiscal.cst_icms_10").id,
                "cst_out_id": cls.env.ref("l10n_br_fiscal.cst_icms_10").id,
            }
        )
        cls.operation = cls.env.ref("l10n_br_fiscal.fo_venda")
        cls.operation_line = cls.env.ref("l10n_br_fiscal.fo_venda_venda")
        tax_def_model = cls.env["l10n_br_fiscal.tax.definition"]
        # IPI out of the way (the IPI of the NCM would enter the ST base):
        # only ICMS and ST on the line.
        cls.product_a.ncm_id.tax_ipi_id = cls.env.ref("l10n_br_fiscal.tax_ipi_nt")
        for group, tax, cst in (
            ("icms", cls.env.ref("l10n_br_fiscal.tax_icms_20"), "cst_icms_10"),
            ("icmsst", icmsst_20_mva_50, "cst_icms_10"),
        ):
            tax_def_model.create(
                {
                    "company_id": cls.company.id,
                    "tax_group_id": cls.env.ref(f"l10n_br_fiscal.tax_group_{group}").id,
                    "is_taxed": True,
                    "is_debit_credit": True,
                    "custom_tax": True,
                    "tax_id": tax.id,
                    "cst_id": cls.env.ref(f"l10n_br_fiscal.{cst}").id,
                    "state": "approved",
                    "fiscal_operation_line_id": cls.operation_line.id,
                }
            )
        cls.operation.with_company(cls.company).deductible_taxes = True

    def _sale_move(self):
        return self.init_invoice(
            "out_invoice",
            products=[self.product_a],
            document_type=self.env.ref("l10n_br_fiscal.document_55"),
            document_serie_id=self.empresa_lc_document_55_serie_1,
            fiscal_operation=self.operation,
            fiscal_operation_lines=[self.operation_line],
        )

    def _product_line(self, move):
        return move.invoice_line_ids.filtered(lambda line: line.product_id)[:1]

    def _tax(self, key):
        return self.env.ref(
            f"l10n_br_coa.{self.company.id}_{key}", raise_if_not_found=False
        ) or self.env.ref(f"account.{self.company.id}_{key}", raise_if_not_found=False)

    def _tax_lines(self, tax, refund=False):
        lines = (
            tax.refund_repartition_line_ids
            if refund
            else tax.invoice_repartition_line_ids
        )
        return lines.filtered(lambda rline: rline.repartition_type == "tax")

    def _account_code(self, tax, refund=False):
        return self._tax_lines(tax, refund).account_id.with_company(self.company).code

    def test_chart_has_the_deductible_icms_st(self):
        """The ST of the sale has its account and its deductible pair."""
        for key, (invoice_code, refund_code) in EXPECTED_ACCOUNTS.items():
            tax = self._tax(key)
            self.assertTrue(tax, f"{key} is missing from the chart")
            deductible = key == ST_DEDUCTIBLE
            self.assertEqual(tax.deductible, deductible)
            self.assertEqual(
                tax.tax_group_id, self._tax(ST_SALE).tax_group_id, f"{key}: group"
            )
            self.assertEqual(
                self._tax_lines(tax).factor_percent,
                -100 if deductible else 100,
                f"{key} has the wrong repartition factor",
            )
            self.assertEqual(
                self._account_code(tax),
                invoice_code + self.account_suffix,
                f"{key}: invoice account",
            )
            self.assertEqual(
                self._account_code(tax, refund=True),
                refund_code + self.account_suffix,
                f"{key}: refund account",
            )
        # The ST of a purchase is part of the cost: it stays without account.
        self.assertFalse(
            self._tax_lines(self._tax("tax_template_in_icms_subist")).account_id
        )

    def test_receivable_equals_invoice_total(self):
        """Sale of 1.000,00 with 100,00 of ICMS ST: the title is 1.100,00."""
        move = self._sale_move()
        line = self._product_line(move)
        # Guard: the ST is really computed, or the test proves nothing.
        self.assertAlmostEqual(line.icms_value, 200.0, places=2)
        self.assertAlmostEqual(line.icmsst_base, 1500.0, places=2)
        self.assertAlmostEqual(line.icmsst_value, 100.0, places=2)
        self.assertTrue(
            line.tax_ids.filtered(
                lambda tax: tax.deductible and tax == self._tax(ST_DEDUCTIBLE)
            ),
            "the deductible ICMS ST is not on the line",
        )
        move.action_post()
        self.assertEqual(move.state, "posted")
        self.assertAlmostEqual(move.amount_total, 1100.0, places=2)
        self.assertAlmostEqual(move.amount_residual, 1100.0, places=2)
        receivable = move.line_ids.filtered(
            lambda aml: aml.account_id.account_type == "asset_receivable"
        )
        self.assertAlmostEqual(sum(receivable.mapped("balance")), 1100.0, places=2)
        # The ST is owed ("a Recolher") and the deductible tax gives it back in
        # the revenue deduction ("ICMS ST s/ Vendas").
        by_code = {}
        for aml in move.line_ids:
            code = aml.account_id.with_company(self.company).code
            by_code[code] = by_code.get(code, 0.0) + aml.balance
        self.assertAlmostEqual(by_code["2.1.7.1.11" + self.account_suffix], -100.0)
        self.assertAlmostEqual(by_code["6.1.1.2.07" + self.account_suffix], 100.0)

    def test_migration_adds_the_pair_to_a_company_loaded_before(self):
        """A company loaded before the fix gets the pair and the ST account."""
        self._tax(ST_DEDUCTIBLE).unlink()
        st_sale = self._tax(ST_SALE)
        (self._tax_lines(st_sale) | self._tax_lines(st_sale, refund=True)).write(
            {"account_id": False}
        )
        self.assertFalse(self._tax(ST_DEDUCTIBLE))

        load_migration().migrate_companies(self.env(su=True))
        self.env.invalidate_all()

        tax = self._tax(ST_DEDUCTIBLE)
        self.assertTrue(tax, "the migration did not create the deductible ICMS ST")
        self.assertTrue(tax.deductible)
        self.assertEqual(self._tax_lines(tax).factor_percent, -100)
        for key, (invoice_code, refund_code) in EXPECTED_ACCOUNTS.items():
            self.assertEqual(
                self._account_code(self._tax(key)),
                invoice_code + self.account_suffix,
                f"{key}: invoice account",
            )
            self.assertEqual(
                self._account_code(self._tax(key), refund=True),
                refund_code + self.account_suffix,
                f"{key}: refund account",
            )

    def test_migration_adopts_the_tax_made_by_hand(self):
        """A deductible ICMS ST created by hand is kept, not duplicated."""
        generated = self._tax(ST_DEDUCTIBLE)
        group = generated.tax_group_id
        generated.unlink()
        by_hand = self.env["account.tax"].create(
            {
                "name": "ICMS ST Saida Dedutivel",
                "company_id": self.company.id,
                "tax_group_id": group.id,
                "type_tax_use": "sale",
                "deductible": True,
                "amount": 0.0,
            }
        )

        load_migration().migrate_companies(self.env(su=True))
        self.env.invalidate_all()

        self.assertEqual(self._tax(ST_DEDUCTIBLE), by_hand)
        self.assertEqual(
            self.env["account.tax"].search_count(
                [
                    ("company_id", "=", self.company.id),
                    ("tax_group_id", "=", group.id),
                    ("type_tax_use", "=", "sale"),
                    ("deductible", "=", True),
                ]
            ),
            1,
        )

    def test_migration_keeps_the_account_already_set(self):
        """The ICMS ST of the sale keeps an account somebody already chose."""
        st_sale = self._tax(ST_SALE)
        other = self.company_data["default_account_tax_sale"]
        self._tax_lines(st_sale).account_id = other

        load_migration().migrate_companies(self.env(su=True))
        self.env.invalidate_all()

        self.assertEqual(self._tax_lines(st_sale).account_id, other)


@tagged("post_install", "-at_install")
class TestIcmsStDeductibleGenericChart(TestIcmsStDeductible):
    """Same flows with the Brazilian generic chart: no suffix on the accounts."""

    allow_inherited_tests_method = True
    chart_template = "br_oca_generic"
    account_suffix = ""
