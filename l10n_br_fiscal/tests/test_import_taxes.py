# Copyright 2026 KMEE (Ygor Carvalho <ygor.carvalho@kmee.com.br>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import TransactionCase


class TestImportTaxes(TransactionCase):
    def test_the_import_contribution_rates_are_in_the_catalog(self):
        """PIS/PASEP and COFINS on imports of goods, Lei 10.865/2004 art. 8.

        Without them there is no tax to carry the amounts the customs
        declaration already charged, so the entry note of an import goes out
        without the two contributions.
        """
        esperado = (
            ("l10n_br_fiscal.tax_pis_importacao_2_10", 2.10, "pis"),
            ("l10n_br_fiscal.tax_cofins_importacao_9_65", 9.65, "cofins"),
        )
        for xmlid, percent, domain in esperado:
            tax = self.env.ref(xmlid)
            self.assertAlmostEqual(tax.percent_amount, percent, places=2, msg=xmlid)
            self.assertEqual(tax.tax_group_id.tax_domain, domain, xmlid)
            self.assertEqual(tax.tax_base_type, "percent", xmlid)

    def test_the_import_rates_credit_on_the_way_in(self):
        """The importer credits the contributions, so the inbound CST is 50."""
        for xmlid in (
            "l10n_br_fiscal.tax_pis_importacao_2_10",
            "l10n_br_fiscal.tax_cofins_importacao_9_65",
        ):
            tax = self.env.ref(xmlid)
            self.assertEqual(tax.cst_in_id.code, "50", xmlid)
