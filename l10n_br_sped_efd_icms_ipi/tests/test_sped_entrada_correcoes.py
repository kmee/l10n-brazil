# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from datetime import datetime

from odoo.exceptions import ValidationError
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

    def test_pulling_twice_does_not_duplicate_the_registers(self):
        """Pull Registers is idempotent: what an earlier pull created is
        replaced, what was typed by hand stays."""
        self._entry_document()
        declaration = self._declaration_july()
        manual = self.env["l10n_br_sped.efd_icms_ipi.0150"].create(
            {"declaration_id": declaration.id, "COD_PART": "manual", "NOME": "Manual"}
        )
        before = {
            model: self.env[f"l10n_br_sped.efd_icms_ipi.{model}"].search_count(
                [("declaration_id", "=", declaration.id)]
            )
            for model in ("c100", "c170", "c190", "0150", "0200")
        }
        declaration.button_populate_sped_from_odoo()
        after = {
            model: self.env[f"l10n_br_sped.efd_icms_ipi.{model}"].search_count(
                [("declaration_id", "=", declaration.id)]
            )
            for model in before
        }
        self.assertEqual(before, after)
        self.assertTrue(manual.exists(), "the register typed by hand is kept")

    def test_the_sped_screens_are_translated_to_portuguese(self):
        self.env["res.lang"]._activate_lang("pt_BR")
        self.env["ir.module.module"].search(
            [("name", "in", ("l10n_br_sped_base", "l10n_br_sped_efd_icms_ipi"))]
        )._update_translations(["pt_BR"])
        model = self.env["l10n_br_sped.efd_icms_ipi.0000"].with_context(lang="pt_BR")
        arch, _view = model._get_view(view_type="form")
        buttons = {
            name: arch.xpath(f"//header/button[@name='{name}']")[0].get("string")
            for name in (
                "button_populate_sped_from_odoo",
                "button_flush_registers",
                "button_done",
                "button_draft",
                "button_create_sped_files",
            )
        }
        self.assertEqual(
            buttons,
            {
                "button_populate_sped_from_odoo": "Puxar Registros do Odoo",
                "button_flush_registers": "Limpar Registros",
                "button_done": "Marcar como Concluída",
                "button_draft": "Voltar para Rascunho",
                "button_create_sped_files": "Gerar Arquivo SPED",
            },
        )
        fields = model.fields_get(["company_id", "debug", "split_sped_by_bloco"])
        self.assertEqual(
            {name: field["string"] for name, field in fields.items()},
            {
                "company_id": "Empresa",
                "debug": "Depuração",
                "split_sped_by_bloco": "Separar SPED por Bloco",
            },
        )
        action = self.env.ref(
            "l10n_br_sped_efd_icms_ipi.declaration_efd_icms_ipi_action"
        )
        self.assertEqual(
            action.with_context(lang="pt_BR").name, "Declaração EFD ICMS/IPI"
        )

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

    def test_a_document_without_access_key_is_left_out_and_listed(self):
        """NF-e without an access key would go out with an empty CHV_NFE and the
        PVA refuses the file: it stays out and the history lists it."""
        keyed, _line = self._entry_document()
        keyless, _line = self._entry_document(document_key=False)
        declaration = self._declaration_july()
        c100 = self._c100(declaration)
        self.assertIn(keyed.document_number, c100)
        self.assertNotIn(keyless.document_number, c100)
        history = " ".join(declaration.message_ids.mapped("body"))
        self.assertIn(keyless.document_number, history)

    def test_dt_e_s_is_never_before_dt_doc(self):
        """An entry date earlier than the emission goes out as the emission."""
        doc, _line = self._entry_document(
            document_date=datetime(2026, 7, 20, 12, 0),
            date_in_out=datetime(2026, 7, 5, 12, 0),
        )
        rec = self._c100(self._declaration_july())[doc.document_number]
        self.assertEqual(rec["DT_DOC"], "20072026")
        self.assertEqual(rec["DT_E_S"], "20072026")
