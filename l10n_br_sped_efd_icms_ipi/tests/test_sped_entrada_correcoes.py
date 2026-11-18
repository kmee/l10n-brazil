# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo.tests.common import tagged

from odoo.addons.l10n_br_tax_assessment.tests.common_entrada import SpedEntradaCommon

from .test_sped_entrada import EntradaHelpers


@tagged("post_install", "-at_install")
class TestSpedEfdIcmsIpiCorrecoes(EntradaHelpers, SpedEntradaCommon):
    """Defects found by running the books through the screens."""

    def test_cod_part_is_the_same_in_the_0150_and_the_c100(self):
        """One rule of COD_PART for the 0150 and for the registers that point to
        it: the id of the partner. The 0150 used the CNPJ and the C100 the id,
        so the C100 pointed to nobody."""
        doc, _line = self._entry_document()
        declaration = self._declaration_july()
        cod_part = self._c100(declaration)[doc.document_number]["COD_PART"]
        self.assertEqual(cod_part, str(doc.partner_id.id))
        self.assertIn(
            cod_part,
            [rec["COD_PART"] for rec in self._sped_records(declaration, "0150")],
        )

    def test_no_c101_without_difal_or_fcp(self):
        """C101 (EC 87/15) only goes out with values, never empty."""
        self._entry_document()
        text = self._declaration_july()._generate_sped_text()
        self.assertIn("|C100|", text)
        self.assertNotIn("|C101|", text)

    def test_c101_goes_out_with_the_difal_values(self):
        self._entry_document(
            line_vals={"icmsfcp_value": 3.0, "icms_destination_value": 5.0}
        )
        c101 = self._sped_records(self._declaration_july(), "C101")
        self.assertEqual(len(c101), 1)
        self.assertEqual(self._number(c101[0]["VL_FCP_UF_DEST"]), 3.0)
        self.assertEqual(self._number(c101[0]["VL_ICMS_UF_DEST"]), 5.0)

    def test_ind_pgto_comes_from_the_installments_of_the_bill(self):
        """On the spot, on terms, without payment: one rule from the
        installments, the same in both SPED."""
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

    def test_the_sped_adjustment_code_is_on_the_benefit_and_relief_screens(self):
        for model, view in (
            ("l10n_br_fiscal.tax.definition", "l10n_br_fiscal.tax_definition_form"),
            ("l10n_br_fiscal.icms.relief", "l10n_br_fiscal.tax_icms_relief_form"),
        ):
            view_id = self.env.ref(view).id
            arch = self.env[model].get_view(view_id)["arch"]
            self.assertIn('name="sped_cod_aj"', arch, model)
        self.env["res.lang"]._activate_lang("pt_BR")
        self.env["ir.module.module"].search(
            [("name", "=", "l10n_br_sped_efd_icms_ipi")]
        )._update_translations(["pt_BR"])
        label = (
            self.env["l10n_br_fiscal.icms.relief"]
            .with_context(lang="pt_BR")
            .fields_get(["sped_cod_aj"])["sped_cod_aj"]["string"]
        )
        self.assertEqual(label, "Código de Ajuste SPED")
