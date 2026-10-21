# Copyright 2026 KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import importlib.util

from odoo import Command
from odoo.modules.module import get_module_path
from odoo.tests import tagged

from .common import AccountMoveBRCommon


@tagged("post_install", "-at_install")
class TestIbsCbsDeductible(AccountMoveBRCommon):
    """IBS and CBS must not inflate the receivable of a deductible operation.

    When the fiscal operation uses deductible taxes the product line takes
    the full document total, and the deductible account tax of each fiscal
    tax gives the amount back with a negative factor. The chart shipped by
    `l10n_br_coa` has to carry the deductible IBS and CBS taxes, otherwise
    the tax is added once more to the receivable and the invoice total no
    longer matches the title.
    """

    chart_template = "generic_coa"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.company_data["company"]
        cls.env["account.chart.template"].load_fiscal_taxes(companies=[cls.company])
        cls.configure_normal_company_taxes()
        tax_def_model = cls.env["l10n_br_fiscal.tax.definition"]
        for group, tax, cst in (
            ("ibs", "tax_ibs_0_1", "cst_ibs_000"),
            ("cbs", "tax_cbs_0_9", "cst_cbs_000"),
        ):
            tax_def_model.create(
                {
                    "company_id": cls.company.id,
                    "tax_group_id": cls.env.ref(f"l10n_br_fiscal.tax_group_{group}").id,
                    "is_taxed": True,
                    "is_debit_credit": True,
                    "custom_tax": True,
                    "tax_id": cls.env.ref(f"l10n_br_fiscal.{tax}").id,
                    "cst_id": cls.env.ref(f"l10n_br_fiscal.{cst}").id,
                    "state": "approved",
                }
            )
        cls.operation = cls.env.ref("l10n_br_fiscal.fo_venda")
        cls.operation.with_company(cls.company).deductible_taxes = True
        cls.term_3x = cls.env["account.payment.term"].create(
            {
                "name": "3 parcelas",
                "company_id": cls.company.id,
                "line_ids": [
                    Command.create(
                        {"value": "percent", "value_amount": 33.33, "nb_days": 30}
                    ),
                    Command.create(
                        {"value": "percent", "value_amount": 33.33, "nb_days": 60}
                    ),
                    Command.create(
                        {"value": "percent", "value_amount": 33.34, "nb_days": 90}
                    ),
                ],
            }
        )

    def _sale_move(self):
        return self.init_invoice(
            "out_invoice",
            products=[self.product_a],
            document_type=self.env.ref("l10n_br_fiscal.document_55"),
            document_serie_id=self.empresa_lc_document_55_serie_1,
            fiscal_operation=self.operation,
            fiscal_operation_lines=[self.env.ref("l10n_br_fiscal.fo_venda_venda")],
        )

    def _product_line(self, move):
        return move.invoice_line_ids.filtered(lambda line: line.product_id)[:1]

    def test_chart_has_the_deductible_taxes(self):
        """The chart carries IBS, CBS and IS, plain and deductible."""
        for group in ("ibs", "cbs", "is"):
            for use in ("out", "in"):
                for suffix in ("", "_deductible"):
                    key = f"tax_template_{use}_{group}{suffix}"
                    tax = self.env.ref(
                        f"l10n_br_coa.{self.company.id}_{key}",
                        raise_if_not_found=False,
                    )
                    self.assertTrue(tax, f"{key} is missing from the chart")
                    self.assertEqual(tax.deductible, bool(suffix))
                    line = tax.invoice_repartition_line_ids.filtered(
                        lambda rline: rline.repartition_type == "tax"
                    )
                    self.assertEqual(
                        line.factor_percent,
                        -100 if suffix else 100,
                        f"{key} has the wrong repartition factor",
                    )

    def test_receivable_equals_invoice_total(self):
        """With deductible taxes the title is the invoice total."""
        move = self._sale_move()
        line = self._product_line(move)
        # Guard: IBS and CBS are really computed, or the test proves nothing.
        self.assertTrue(line.ibs_value, "IBS was not computed")
        self.assertTrue(line.cbs_value, "CBS was not computed")
        self.assertTrue(
            line.tax_ids.filtered(lambda tax: tax.deductible and "IBS" in tax.name),
            "the deductible IBS tax is not on the line",
        )
        move.action_post()
        self.assertEqual(move.state, "posted")
        self.assertAlmostEqual(move.amount_residual, move.amount_total, places=2)

    def test_payment_term_in_three_installments_posts(self):
        """Splitting the title in three keeps the entry balanced."""
        move = self._sale_move()
        move.invoice_payment_term_id = self.term_3x
        move.action_post()
        self.assertEqual(move.state, "posted")
        receivable = move.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        self.assertEqual(len(receivable), 3)
        self.assertAlmostEqual(
            sum(receivable.mapped("balance")), move.amount_total, places=2
        )
        self.assertAlmostEqual(move.amount_residual, move.amount_total, places=2)

    def test_migration_links_the_is_group_to_the_fiscal_group(self):
        """Only the IS group is linked; the other groups are left alone."""
        path = get_module_path("l10n_br_account")
        spec = importlib.util.spec_from_file_location(
            "l10n_br_account_post_migration_18_0_3_9_0",
            f"{path}/migrations/18.0.3.9.0/post-migration.py",
        )
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)

        group_is = self.env.ref(f"l10n_br_coa.{self.company.id}_tax_group_is")
        group_issqn = self.env.ref(f"l10n_br_coa.{self.company.id}_tax_group_issqn")
        fiscal_issqn = group_issqn.fiscal_tax_group_id
        self.assertEqual(
            group_is.fiscal_tax_group_id, self.env.ref("l10n_br_fiscal.tax_group_is")
        )
        group_is.fiscal_tax_group_id = False
        group_issqn.fiscal_tax_group_id = False

        migration.migrate(self.env.cr, "18.0.3.8.1")
        self.env.invalidate_all()

        self.assertEqual(
            group_is.fiscal_tax_group_id, self.env.ref("l10n_br_fiscal.tax_group_is")
        )
        self.assertFalse(group_issqn.fiscal_tax_group_id)
        self.assertTrue(fiscal_issqn)
