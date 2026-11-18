# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo.tests.common import tagged

from odoo.addons.l10n_br_tax_assessment.tests.common_entrada import SpedEntradaCommon

from .test_sped_entrada import SpedPisCofinsEntradaMixin


@tagged("post_install", "-at_install")
class TestSpedPisCofinsCorrecoes(SpedPisCofinsEntradaMixin, SpedEntradaCommon):
    """Defects found by running the books through the screens."""

    def test_cod_part_is_the_same_in_the_0150_and_the_c100(self):
        doc, _line = self._entry_document()
        declaration = self._declaration_july()
        cod_part = self._c100(declaration)[doc.document_number]["COD_PART"]
        self.assertEqual(cod_part, str(doc.partner_id.id))
        self.assertIn(
            cod_part,
            [rec["COD_PART"] for rec in self._sped_records(declaration, "0150")],
        )

    def test_ind_pgto_comes_from_the_installments_of_the_bill(self):
        cash = self._purchase_move(
            "fo_compras_compras_comercializacao",
            "301",
            payment_term="account_payment_term_immediate",
        )
        term = self._purchase_move(
            "fo_compras_compras_comercializacao",
            "302",
            payment_term="account_payment_term_30days",
        )
        free, _line = self._entry_document()
        c100 = self._c100(self._declaration_july())
        self.assertEqual(c100[cash.fiscal_document_id.document_number]["IND_PGTO"], "0")
        self.assertEqual(c100[term.fiscal_document_id.document_number]["IND_PGTO"], "1")
        self.assertEqual(c100[free.document_number]["IND_PGTO"], "9")

    def test_pulling_twice_does_not_duplicate_the_registers(self):
        self._entry_document()
        declaration = self._declaration_july()
        models = ("c100", "c170", "0150", "0200")
        before = {
            model: self.env[f"l10n_br_sped.efd_pis_cofins.{model}"].search_count(
                [("declaration_id", "=", declaration.id)]
            )
            for model in models
        }
        declaration.button_populate_sped_from_odoo()
        after = {
            model: self.env[f"l10n_br_sped.efd_pis_cofins.{model}"].search_count(
                [("declaration_id", "=", declaration.id)]
            )
            for model in models
        }
        self.assertEqual(before, after)
