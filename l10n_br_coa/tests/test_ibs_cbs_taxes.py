# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

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
