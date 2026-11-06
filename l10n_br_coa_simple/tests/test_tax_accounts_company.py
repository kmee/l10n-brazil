# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests import TransactionCase, tagged

# tax template -> (invoice account, refund account): accounts of the chart,
# ITG 1000 (2022) Anexo 7, by exact code
EXPECTED = {
    "tax_template_out_icms": ("2.1.4.02.06", "1.1.2.05.02"),
    "tax_template_in_icms": ("1.1.2.05.02", "2.1.4.02.06"),
    "tax_template_out_ipi": ("2.1.4.02.05", "1.1.2.05.01"),
    "tax_template_in_ipi": ("1.1.2.05.01", "2.1.4.02.05"),
    "tax_template_out_pis": ("2.1.4.02.03", "1.1.2.05.03"),
    "tax_template_in_pis": ("1.1.2.05.03", "2.1.4.02.03"),
    "tax_template_out_cofins": ("2.1.4.02.04", "1.1.2.05.05"),
    "tax_template_out_issqn": ("2.1.4.02.08", "1.1.2.04.06"),
    "tax_template_in_issqn": ("1.1.2.04.06", "2.1.4.02.08"),
    "tax_template_out_icmssn": ("2.1.4.02.10", "1.1.2.05.02"),
    "tax_template_icms_out_deductible": ("3.1.2.01.04", "3.1.2.01.04"),
    "tax_template_icms_in_deductible": ("3.1.2.01.04", "2.1.4.02.06"),
    "tax_template_out_ipi_deductible": ("3.1.2.01.09", "3.1.2.01.09"),
    "tax_template_out_pis_deductible": ("3.1.2.01.01", "3.1.2.01.01"),
    "tax_template_cofins_out_deductible": ("3.1.2.01.02", "3.1.2.01.02"),
    "tax_template_out_pis_wh": ("1.1.2.05.03", "2.1.4.02.03"),
    "tax_template_out_irpj_wh": ("1.1.2.04.01", "2.1.4.01.01"),
    "tax_template_in_irpj_wh": ("2.1.4.01.01", "1.1.2.04.01"),
    "tax_template_out_csll_wh": ("1.1.2.04.02", "2.1.4.01.02"),
    "tax_template_out_inss_wh": ("1.1.2.04.05", "2.1.4.01.04"),
    "tax_template_out_issqn_wh": ("1.1.2.04.06", "2.1.4.02.08"),
}


@tagged("post_install", "-at_install")
class TestTaxAccountsCompany(TransactionCase):
    """The default tax accounts are the accounts of the chart.

    The ITG codes of the default tax accounts were the ones of the ITG 1000 of
    2012. The chart is the Anexo 7 of the ITG 1000 of 2022, so none of them
    existed and the load created a copy with the review suffix for each one,
    in the wrong group (the ICMS payable, 2.1.3.02, under "Emprestimos e
    Financiamentos"). The code of an account also belongs to a company, so
    the search has to run in the company being loaded, not in the one of the
    user.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # The user company is NOT the one being loaded: this is what makes the
        # search look at the wrong company.
        cls.chart = cls.env["account.chart.template"]
        vals = {
            "name": "Empresa Plano Simples",
            "country_id": cls.env.ref("base.br").id,
            "currency_id": cls.env.ref("base.BRL").id,
        }
        if "tax_framework" in cls.env["res.company"]._fields:
            vals["tax_framework"] = "1"  # Simples Nacional: ITG codes
        cls.company = cls.env["res.company"].create(vals)
        cls.env.user.company_ids |= cls.company
        cls.chart.try_loading("br_oca_simple", cls.company, install_demo=False)

    def _codes(self):
        accounts = (
            self.env["account.account"]
            .with_company(self.company)
            .search([("company_ids", "in", self.company.id)])
        )
        return accounts.mapped("code")

    def _tax_codes(self, key):
        tax = self.env.ref(
            f"account.{self.company.id}_{key}", raise_if_not_found=False
        ) or self.env.ref(f"l10n_br_coa.{self.company.id}_{key}")
        codes = []
        for lines in (
            tax.invoice_repartition_line_ids,
            tax.refund_repartition_line_ids,
        ):
            line = lines.filtered(lambda line: line.repartition_type == "tax")
            codes.append(line.account_id.with_company(self.company).code)
        return tuple(codes)

    def test_taxes_use_the_chart_accounts(self):
        self.assertEqual(self.company.chart_template, "br_oca_simple")
        for key, expected in EXPECTED.items():
            self.assertEqual(self._tax_codes(key), expected, key)

    def test_no_account_beside_the_chart_ones(self):
        """No `.GEN` or `.BR` copy, and no account for a key the chart lacks."""
        codes = self._codes()
        self.assertFalse([code for code in codes if code.endswith((".GEN", ".BR"))])
        # a key without an ITG code used to become a "None.GEN" account
        self.assertFalse([code for code in codes if code.startswith("None")])
        self.assertEqual(len(codes), len(set(codes)))

    def test_no_second_set_of_accounts(self):
        """Running the population again creates nothing and changes nothing."""
        before = sorted(self._codes())
        taxes = {key: self._tax_codes(key) for key in EXPECTED}
        self.chart._populate_default_br_tax_accounts(self.company, flavor="itg")
        self.assertEqual(sorted(self._codes()), before)
        self.assertEqual({key: self._tax_codes(key) for key in EXPECTED}, taxes)
