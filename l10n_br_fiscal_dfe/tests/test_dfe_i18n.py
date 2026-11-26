# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestDfeI18n(TransactionCase):
    """The pt_BR terms of the import window and of the inbox are loaded."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("pt_BR")
        cls.env["ir.module.module"]._load_module_terms(
            ["l10n_br_fiscal_edi", "l10n_br_fiscal_dfe"], ["pt_BR"], overwrite=True
        )

    def test_the_import_window_is_in_portuguese(self):
        wizard = self.env["l10n_br_fiscal_edi.document.import.wizard"].with_context(
            lang="pt_BR"
        )
        fields_info = wizard.fields_get(["access_key"])
        self.assertEqual(fields_info["access_key"]["string"], "Chave de Acesso")
        arch = wizard.get_view(view_type="form")["arch"]
        self.assertIn("Cancelar", arch)
        self.assertNotIn('string="Cancel"', arch)

    def test_the_inbox_columns_are_in_portuguese(self):
        inbox = self.env["l10n_br_fiscal_dfe.document"].with_context(lang="pt_BR")
        fields_info = inbox.fields_get(["utilization", "import_block_reason"])
        self.assertEqual(fields_info["utilization"]["string"], "Utilização")
        self.assertEqual(
            fields_info["import_block_reason"]["string"], "Motivo do bloqueio"
        )
        selection = dict(fields_info["utilization"]["selection"])
        self.assertEqual(selection["available"], "Disponível")
        self.assertEqual(selection["posted"], "Lançada")
