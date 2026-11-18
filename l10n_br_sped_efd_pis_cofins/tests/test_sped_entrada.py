# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from datetime import date

from odoo.tests.common import tagged

from odoo.addons.l10n_br_tax_assessment.tests.common_entrada import SpedEntradaCommon


class SpedPisCofinsEntradaMixin:
    def _declaration_july(self):
        return self._declaration("efd_pis_cofins", date(2026, 7, 1), date(2026, 7, 31))

    def _c100(self, declaration):
        """{NUM_DOC: C100} of the generated file."""
        return {rec["NUM_DOC"]: rec for rec in self._sped_records(declaration, "C100")}


@tagged("post_install", "-at_install")
class TestSpedPisCofinsEntrada(SpedPisCofinsEntradaMixin, SpedEntradaCommon):
    """How the EFD Contribuicoes books a supplier invoice (the entry)."""

    def test_c100_cod_sit_follows_the_state_of_the_document(self):
        regular, _line = self._entry_document()
        cancelled, _line = self._entry_document(state_edoc="cancelada")
        denied, _line = self._entry_document(state_edoc="denegada")
        unused, _line = self._entry_document(state_edoc="inutilizada")
        complementary, _line = self._entry_document(edoc_purpose="2")
        c100 = self._c100(self._declaration_july())
        self.assertEqual(
            {
                doc.document_number: c100[doc.document_number]["COD_SIT"]
                for doc in (regular, cancelled, denied, unused, complementary)
            },
            {
                regular.document_number: "00",
                cancelled.document_number: "02",
                denied.document_number: "04",
                unused.document_number: "05",
                complementary.document_number: "06",
            },
        )

    def test_c100_of_a_cancelled_document_only_has_what_the_guide_allows(self):
        cancelled, _line = self._entry_document(state_edoc="cancelada")
        declaration = self._declaration_july()
        rec = self._c100(declaration)[cancelled.document_number]
        self.assertEqual(rec["COD_SIT"], "02")
        self.assertEqual(rec["CHV_NFE"], cancelled.document_key)
        for name in ("COD_PART", "DT_DOC", "DT_E_S", "VL_DOC", "VL_PIS", "VL_COFINS"):
            self.assertEqual(rec[name], "", f"{name} must be blank")
        self.assertNotIn("|C170|", declaration._generate_sped_text())

    def _c170(self, declaration):
        records = self._sped_records(declaration, "C170")
        self.assertEqual(len(records), 1)
        return records[0]

    @staticmethod
    def _number(text):
        return float(text.replace(",", ".") or 0)
