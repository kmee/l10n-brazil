# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo.tests.common import tagged

from odoo.addons.l10n_br_tax_assessment.tests.common_entrada import SpedEntradaCommon

from .test_sped_entrada import EntradaHelpers


@tagged("post_install", "-at_install")
class TestSpedEfdIcmsIpiIpiEntrada(EntradaHelpers, SpedEntradaCommon):
    """IPI of the entry, own issue and complementary information in the books."""

    def test_the_ipi_of_an_entry_without_credit_stays_out_of_the_books(self):
        """Resale does not credit the IPI (only the industrialization does): the
        C170, the C190 and the E510 carry CST 49 and no IPI, so they sum what
        the E520 credits."""
        resale = self._purchase_move("fo_compras_compras_comercializacao", "611")
        industrialization = self._purchase_move("fo_compras_compras", "612")
        declaration = self._declaration_july()
        c170 = {rec["CFOP"]: rec for rec in self._sped_records(declaration, "C170")}
        by_cfop = {
            "2102": self._number(c170["2102"]["VL_IPI"]),
            "2101": self._number(c170["2101"]["VL_IPI"]),
        }
        self.assertEqual(by_cfop["2102"], 0.0, "resale: IPI in the cost")
        self.assertGreater(by_cfop["2101"], 0.0, "industrialization credits it")
        self.assertEqual(c170["2102"]["CST_IPI"], "49")
        self.assertEqual(c170["2102"]["COD_ENQ"], "")
        c190 = self._sped_records(declaration, "C190")
        self.assertAlmostEqual(
            sum(self._number(rec["VL_IPI"]) for rec in c190), by_cfop["2101"], places=2
        )
        e510 = self._sped_records(declaration, "E510")
        self.assertAlmostEqual(
            sum(self._number(rec["VL_IPI"]) for rec in e510), by_cfop["2101"], places=2
        )
        self.assertIn("49", [rec["CST_IPI"] for rec in e510])
        c100 = self._c100(declaration)
        self.assertEqual(
            self._number(c100[resale.fiscal_document_id.document_number]["VL_IPI"]),
            0.0,
        )
        self.assertGreater(
            self._number(
                c100[industrialization.fiscal_document_id.document_number]["VL_IPI"]
            ),
            0.0,
        )

    def test_an_nfe_issued_by_the_company_has_no_c170(self):
        """The Guia Pratico: C100 and C190 only for an own issue."""
        sale, _line = self._entry_document(
            operation="fo_venda", operation_line="fo_venda_venda", imported=False
        )
        declaration = self._declaration_july()
        self.assertIn(sale.document_number, self._c100(declaration))
        self.assertEqual(self._sped_records(declaration, "C170"), [])
        self.assertTrue(self._sped_records(declaration, "C190"))

    def test_no_0450_without_a_register_that_refers_to_it(self):
        """The PVA refuses a 0450 that nothing points to."""
        doc, _line = self._entry_document()
        doc.comment_ids = [
            (6, 0, self.env["l10n_br_fiscal.comment"].search([], limit=1).ids)
        ]
        declaration = self._declaration_july()
        self.assertEqual(self._sped_records(declaration, "0450"), [])

    def test_0400_only_lists_the_natures_an_item_points_to(self):
        """The natureza of an own issue (no C170) is not declared: the PVA
        refuses a 0400 that no register refers to."""
        self._entry_document()
        self._entry_document(
            operation="fo_venda", operation_line="fo_venda_venda", imported=False
        )
        declaration = self._declaration_july()
        codes = [rec["COD_NAT"] for rec in self._sped_records(declaration, "0400")]
        self.assertEqual(codes, [self.env.ref("l10n_br_fiscal.fo_compras").code])
