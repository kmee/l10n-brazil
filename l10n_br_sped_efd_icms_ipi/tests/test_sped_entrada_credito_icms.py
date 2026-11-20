# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo.tests.common import tagged

from odoo.addons.l10n_br_tax_assessment.tests.common_entrada import SpedEntradaCommon

from .test_sped_entrada import EntradaHelpers


@tagged("post_install", "-at_install")
class TestSpedEntradaCreditoIcms(EntradaHelpers, SpedEntradaCommon):
    """The ICMS credit of the assessment (E110) is the one of the entry C190.

    Use and consumption (CFOP 1556/2556) gives no ICMS credit (LC 87/1996,
    art. 33, I): the C190 carries it without credit and the vendor bill books
    no ICMS to recover, so the assessment, which reads the ledger, does not
    credit it either. The PVA crosses E110 field 5 with the C190.
    """

    def setUp(self):
        super().setUp()
        if "stock_valuation_via_stock_price" not in self.company._fields:
            self.skipTest("l10n_br_stock_account is not installed")
        self.company.stock_valuation_via_stock_price = True

    def _icms_lines(self, move):
        return move.line_ids.filtered(
            lambda line: line.tax_line_id.tax_group_id.fiscal_tax_group_id.tax_domain
            == "icms"
        )

    def test_e110_credit_of_a_use_and_consumption_purchase(self):
        resale = self._purchase_move("fo_compras_compras_comercializacao", "801")
        consumption = self._purchase_move("fo_compras_compras_uso_consumo", "802")
        consumption_line = consumption.invoice_line_ids.filtered("product_id")
        self.assertIn(consumption_line.cfop_id.code, ("1556", "2556"))
        self.assertGreater(consumption_line.icms_value, 0, "the note has ICMS")
        self.assertFalse(self._icms_lines(consumption), "no ICMS to recover")
        self.assertTrue(self._icms_lines(resale))
        self._assess_icms_of_july()
        declaration = self._declaration_july()
        c190_credit = sum(
            self._number(rec["VL_ICMS"])
            for rec in self._sped_records(declaration, "C190")
            if rec["CFOP"].startswith(("1", "2", "3"))
        )
        self.assertAlmostEqual(
            c190_credit,
            resale.invoice_line_ids.filtered("product_id").icms_value,
            places=2,
        )
        e110 = self._sped_records(declaration, "E110")
        self.assertEqual(len(e110), 1)
        self.assertAlmostEqual(
            self._number(e110[0]["VL_TOT_CREDITOS"]), c190_credit, places=2
        )
