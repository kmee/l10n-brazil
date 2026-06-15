# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase


class TestSpedEFDPISCOFINS(TransactionCase):
    """Bootstrap smoke tests for the EFD Contribuições wiring."""

    def _declaration(self):
        return self.env["l10n_br_sped.efd_pis_cofins.0000"].create(
            {"company_id": self.env.company.id}
        )

    def test_spec_model_is_registered(self):
        self.assertIn("l10n_br_sped.efd_pis_cofins.6.0000", self.env)
        self.assertIn("l10n_br_sped.mixin.efd_pis_cofins", self.env)

    def test_declaration_kind_and_creation(self):
        declaration = self._declaration()
        self.assertEqual(declaration._get_kind(), "efd_pis_cofins")
        self.assertEqual(declaration.state, "draft")

    def test_map_0000_company(self):
        declaration = self._declaration()
        vals = declaration._map_from_odoo(self.env.company, None, declaration)
        self.assertEqual(vals["COD_VER"], "006")
        self.assertEqual(vals["TIPO_ESCRIT"], "0")

    def test_full_pipeline_headless(self):
        """Pull from Odoo and generate the file with no UI interaction."""
        declaration = self._declaration()
        declaration.button_populate_sped_from_odoo()
        self.assertEqual(declaration.COD_VER, "006")
        declaration.button_create_sped_files()
        attachment = self.env["ir.attachment"].search(
            [("res_model", "=", declaration._name), ("res_id", "=", declaration.id)],
            limit=1,
        )
        self.assertTrue(attachment)
