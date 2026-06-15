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

    def test_map_0005_company_complementary(self):
        """Register 0005 maps the company complementary data (Bloco 0)."""
        company = self.env.company
        company.write({"name": "ACME Industria", "district": "Centro"})
        declaration = self.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {"company_id": company.id}
        )
        reg = self.env["l10n_br_sped.efd_icms_ipi.0005"]
        vals = reg._map_from_odoo(company, declaration, declaration)
        self.assertEqual(vals["FANTASIA"], "ACME Industria")
        self.assertEqual(vals["BAIRRO"], "Centro")
        self.assertEqual(set(vals), {
            "FANTASIA", "CEP", "END", "NUM", "COMPL", "BAIRRO", "FONE", "FAX", "EMAIL",
        })

    def test_map_0190_uom(self):
        """Register 0190 maps the unit of measure code and description."""
        uom = self.env.ref("uom.product_uom_unit")
        uom.write({"code": "UN", "description": "Unidade"})
        declaration = self.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {"company_id": self.env.company.id}
        )
        reg = self.env["l10n_br_sped.efd_icms_ipi.0190"]
        vals = reg._map_from_odoo(uom, declaration, declaration)
        self.assertEqual(vals["UNID"], "UN")
        self.assertEqual(vals["DESCR"], "Unidade")

    def _declaration(self):
        return self.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {"company_id": self.env.company.id}
        )

    def test_map_0150_partner(self):
        """Register 0150 maps a participant (res.partner)."""
        partner = self.env["res.partner"].create(
            {"name": "Fornecedor X", "is_company": True, "district": "Industrial"}
        )
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.0150"]._map_from_odoo(
            partner, declaration, declaration
        )
        self.assertEqual(vals["COD_PART"], str(partner.id))
        self.assertEqual(vals["NOME"], "Fornecedor X")
        self.assertEqual(vals["BAIRRO"], "Industrial")
        self.assertEqual(vals["CPF"], "")

    def test_map_0200_product(self):
        """Register 0200 maps a product (product.product)."""
        product = self.env["product.product"].create(
            {"name": "Produto Z", "default_code": "PZ"}
        )
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.0200"]._map_from_odoo(
            product, declaration, declaration
        )
        self.assertEqual(vals["COD_ITEM"], "PZ")
        self.assertEqual(vals["DESCR_ITEM"], "Produto Z")
        self.assertTrue(vals["UNID_INV"])

    def test_map_0400_operation(self):
        """Register 0400 maps a fiscal operation nature."""
        operation = self.env["l10n_br_fiscal.operation"].new({"name": "Venda Test"})
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.0400"]._map_from_odoo(
            operation, declaration, declaration
        )
        self.assertEqual(vals["DESCR_NAT"], "Venda Test")

    def test_map_0450_comment(self):
        """Register 0450 maps a fiscal complementary information."""
        comment = self.env["l10n_br_fiscal.comment"].new(
            {"name": "Obs Test", "comment": "Texto da observacao"}
        )
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.0450"]._map_from_odoo(
            comment, declaration, declaration
        )
        self.assertEqual(vals["TXT"], "Texto da observacao")

    def test_map_0220_uom_conversion(self):
        """Register 0220 computes the conversion factor to the inventory unit."""
        unit = self.env.ref("uom.product_uom_unit")
        dozen = self.env.ref("uom.product_uom_dozen")
        dozen.code = "DUZIA"
        product = self.env["product.product"].create(
            {"name": "Caixa", "uom_id": unit.id}
        )
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.0220"]._map_from_odoo(
            {"uom_id": dozen.id}, product, declaration
        )
        self.assertEqual(vals["UNID_CONV"], "DUZIA")
        self.assertEqual(vals["FAT_CONV"], 12.0)
