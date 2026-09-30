# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLoadFiscalTaxes(TransactionCase):
    def test_load_fiscal_taxes_for_another_company(self):
        """account.account.code is company dependent since 20.0: the tax
        accounts of a company must be found (and not created twice) when the
        fiscal taxes are loaded again from another active company."""
        company = self.env["res.company"].create(
            {
                "name": "BR Tax Accounts",
                "country_id": self.env.ref("base.br").id,
                "currency_id": self.env.ref("base.BRL").id,
            }
        )
        self.assertNotEqual(self.env.company, company)
        chart = self.env["account.chart.template"]
        chart._load("generic_coa", company, install_demo=False)
        chart.load_fiscal_taxes([company])
        # a second load (demo data, tests, chart reload) must reuse them
        chart.load_fiscal_taxes([company])
        accounts = (
            self.env["account.account"]
            .with_company(company)
            .search([("company_ids", "in", company.ids), ("code", "=like", "%.BR")])
        )
        self.assertTrue(accounts)
        codes = accounts.mapped("code")
        self.assertEqual(len(codes), len(set(codes)))
