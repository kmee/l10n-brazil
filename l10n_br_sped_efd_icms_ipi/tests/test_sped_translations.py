# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from datetime import date

from odoo.tests.common import tagged

from odoo.addons.l10n_br_tax_assessment.tests.common_entrada import SpedEntradaCommon


@tagged("post_install", "-at_install")
class TestSpedEfdIcmsIpiTranslations(SpedEntradaCommon):
    """The state bar and the history of the declaration speak Portuguese."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("pt_BR")
        cls.env["ir.module.module"]._load_module_terms(
            ["l10n_br_sped_base", "l10n_br_sped_efd_icms_ipi"],
            ["pt_BR"],
            overwrite=True,
        )

    def _state_labels(self):
        selections = self.env["ir.model.fields.selection"].search(
            [
                ("field_id.model", "=", "l10n_br_sped.efd_icms_ipi.0000"),
                ("field_id.name", "=", "state"),
            ]
        )
        return {
            selection.value: selection.with_context(lang="pt_BR").name
            for selection in selections
        }

    def test_the_state_bar_is_in_portuguese(self):
        self.assertEqual(
            self._state_labels(), {"draft": "Rascunho", "done": "Concluída"}
        )

    def test_the_history_of_the_pull_is_in_portuguese(self):
        self.env["l10n_br_sped.mixin"]._flush_registers("efd_icms_ipi")
        declaration = self.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {
                "company_id": self.company.id,
                "DT_INI": date(2026, 7, 1),
                "DT_FIN": date(2026, 7, 31),
            }
        )
        declaration.with_context(lang="pt_BR").button_populate_sped_from_odoo()
        self.assertIn("Registros puxados do Odoo", declaration.message_ids[0].body)
