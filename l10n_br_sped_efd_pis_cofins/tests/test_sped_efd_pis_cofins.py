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

    def test_map_0110_regime(self):
        """Register 0110 maps the assessment regime (Bloco 0)."""
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.0110"]._map_from_odoo(
            None, None, declaration
        )
        self.assertEqual(vals["COD_INC_TRIB"], "1")

    def test_map_0140_establishment(self):
        """Register 0140 maps the establishment from the company."""
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.0140"]._map_from_odoo(
            self.env.company, None, declaration
        )
        self.assertEqual(vals["COD_EST"], str(self.env.company.id))
        self.assertIn("CNPJ", vals)

    def test_map_0150_partner(self):
        """Register 0150 maps a participant (res.partner)."""
        partner = self.env["res.partner"].create(
            {"name": "Fornecedor P", "is_company": True}
        )
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.0150"]._map_from_odoo(
            partner, None, declaration
        )
        self.assertEqual(vals["COD_PART"], str(partner.id))
        self.assertEqual(vals["NOME"], "Fornecedor P")

    def test_map_0190_uom(self):
        """Register 0190 maps the unit of measure."""
        uom = self.env.ref("uom.product_uom_unit")
        uom.write({"code": "UN", "description": "Unidade"})
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.0190"]._map_from_odoo(
            uom, None, declaration
        )
        self.assertEqual(vals["UNID"], "UN")

    def test_map_0200_product(self):
        """Register 0200 maps a product."""
        product = self.env["product.product"].create(
            {"name": "Produto P", "default_code": "PP"}
        )
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.0200"]._map_from_odoo(
            product, None, declaration
        )
        self.assertEqual(vals["COD_ITEM"], "PP")
        self.assertEqual(vals["DESCR_ITEM"], "Produto P")

    def test_map_c010_establishment(self):
        """Register C010 opens the goods block for the establishment."""
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.c010"]._map_from_odoo(
            self.env.company, None, declaration
        )
        self.assertEqual(vals["IND_ESCRI"], "1")
        self.assertIn("CNPJ", vals)

    def test_map_c100_document(self):
        """Register C100 maps a fiscal document (NF-e) header."""
        partner = self.env["res.partner"].create(
            {"name": "Cliente PC", "is_company": True}
        )
        document = self.env["l10n_br_fiscal.document"].new(
            {"partner_id": partner.id, "document_serie": "1", "document_number": "77"}
        )
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.c100"]._map_from_odoo(
            document, None, declaration
        )
        self.assertEqual(vals["COD_PART"], str(partner.id))
        self.assertEqual(vals["NUM_DOC"], "77")
        self.assertIn("VL_PIS", vals)

    def test_map_c170_line(self):
        """Register C170 maps a document line with PIS/COFINS fields."""
        product = self.env["product.product"].create(
            {"name": "Item PC", "default_code": "IPC"}
        )
        line = self.env["l10n_br_fiscal.document.line"].new(
            {"product_id": product.id, "name": "Item PC desc"}
        )
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.c170"]._map_from_odoo(
            line, None, declaration, index=0
        )
        self.assertEqual(vals["NUM_ITEM"], 1)
        self.assertEqual(vals["COD_ITEM"], "IPC")
        self.assertIn("CST_PIS", vals)
        self.assertIn("CST_COFINS", vals)

    # ------------------------------------------------------------------
    # Bloco M (PIS/COFINS assessment)
    # ------------------------------------------------------------------
    def test_map_m200_pis_consolidation(self):
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.m200"]._map_from_odoo(
            {"deb": 1000.0, "cred": 300.0}, None, declaration
        )
        self.assertEqual(vals["VL_TOT_CONT_NC_PER"], 1000.0)
        self.assertEqual(vals["VL_TOT_CRED_DESC"], 300.0)
        self.assertEqual(vals["VL_TOT_CONT_REC"], 700.0)

    def test_map_m210_pis_detail(self):
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.m210"]._map_from_odoo(
            {"aliq": 1.65, "vl_bc": 1000.0, "vl_cont": 16.5}, None, declaration
        )
        self.assertEqual(vals["ALIQ_PIS"], 1.65)
        self.assertEqual(vals["VL_CONT_PER"], 16.5)

    def test_map_m100_pis_credit(self):
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.m100"]._map_from_odoo(
            {"aliq": 1.65, "vl_bc": 500.0, "vl_cont": 8.25}, None, declaration
        )
        self.assertEqual(vals["COD_CRED"], "101")
        self.assertEqual(vals["VL_CRED"], 8.25)

    def test_map_m600_cofins_consolidation(self):
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.m600"]._map_from_odoo(
            {"deb": 2000.0, "cred": 500.0}, None, declaration
        )
        self.assertEqual(vals["VL_TOT_CONT_REC"], 1500.0)

    def test_map_m610_cofins_detail(self):
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.m610"]._map_from_odoo(
            {"aliq": 7.6, "vl_bc": 1000.0, "vl_cont": 76.0}, None, declaration
        )
        self.assertEqual(vals["ALIQ_COFINS"], 7.6)
        self.assertEqual(vals["VL_CONT_PER"], 76.0)

    def test_map_m500_cofins_credit(self):
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.m500"]._map_from_odoo(
            {"aliq": 7.6, "vl_bc": 500.0, "vl_cont": 38.0}, None, declaration
        )
        self.assertEqual(vals["VL_CRED"], 38.0)

    # ------------------------------------------------------------------
    # Bloco D (transport services)
    # ------------------------------------------------------------------
    def test_map_d010_establishment(self):
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.d010"]._map_from_odoo(
            self.env.company, None, declaration
        )
        self.assertIn("CNPJ", vals)

    def test_map_d100_cte(self):
        partner = self.env["res.partner"].create(
            {"name": "Transp PC", "is_company": True}
        )
        document = self.env["l10n_br_fiscal.document"].new(
            {"partner_id": partner.id, "document_serie": "1", "document_number": "9"}
        )
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_pis_cofins.d100"]._map_from_odoo(
            document, None, declaration
        )
        self.assertEqual(vals["COD_PART"], str(partner.id))
        self.assertEqual(vals["NUM_DOC"], "9")
        self.assertIn("CHV_CTE", vals)
