# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase


class TestSpedEFDICMSIPI(TransactionCase):
    """Bootstrap smoke tests for the EFD ICMS/IPI wiring on l10n_br_sped_base."""

    def test_spec_model_is_registered(self):
        """The generated layout-020 spec for register 0000 must be loaded."""
        self.assertIn("l10n_br_sped.efd_icms_ipi.20.0000", self.env)
        self.assertIn("l10n_br_sped.mixin.efd_icms_ipi", self.env)

    def test_declaration_kind_and_creation(self):
        """A 0000 declaration is creatable and resolves its SPED kind."""
        declaration = self.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {"company_id": self.env.company.id}
        )
        self.assertEqual(declaration._get_kind(), "efd_icms_ipi")
        self.assertEqual(declaration.state, "draft")

    def test_map_from_odoo_company(self):
        """Register 0000 maps the company identification fields."""
        declaration = self.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {"company_id": self.env.company.id}
        )
        vals = declaration._map_from_odoo(self.env.company, None, declaration)
        self.assertEqual(vals["COD_VER"], "020")
        self.assertEqual(vals["IND_ATIV"], "0")
