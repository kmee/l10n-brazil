# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from datetime import datetime

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

    def test_a_document_without_access_key_is_left_out_and_listed(self):
        keyed, _line = self._entry_document()
        keyless, _line = self._entry_document(document_key=False)
        declaration = self._declaration_july()
        c100 = self._c100(declaration)
        self.assertIn(keyed.document_number, c100)
        self.assertNotIn(keyless.document_number, c100)
        history = " ".join(declaration.message_ids.mapped("body"))
        self.assertIn(keyless.document_number, history)

    def test_dt_e_s_is_never_before_dt_doc(self):
        doc, _line = self._entry_document(
            document_date=datetime(2026, 7, 20, 12, 0),
            date_in_out=datetime(2026, 7, 5, 12, 0),
        )
        rec = self._c100(self._declaration_july())[doc.document_number]
        self.assertEqual(rec["DT_E_S"], "20072026")

    def test_the_declaration_title_is_translated_to_portuguese(self):
        self.env["res.lang"]._activate_lang("pt_BR")
        self.env["ir.module.module"].search(
            [("name", "=", "l10n_br_sped_efd_pis_cofins")]
        )._update_translations(["pt_BR"])
        action = self.env.ref(
            "l10n_br_sped_efd_pis_cofins.declaration_efd_pis_cofins_action"
        )
        self.assertEqual(
            action.with_context(lang="pt_BR").name, "Declaração EFD PIS/COFINS"
        )
