# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import tempfile

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

    def test_map_0002_industrial_classification(self):
        """Register 0002 (mandatory for industry) maps the declaration config."""
        declaration = self.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {"company_id": self.env.company.id, "CLAS_ESTAB_IND": "00"}
        )
        reg = self.env["l10n_br_sped.efd_icms_ipi.0002"]
        vals = reg._map_from_odoo(self.env.company, declaration, declaration)
        self.assertEqual(vals["CLAS_ESTAB_IND"], "00")
        self.assertEqual(reg._odoo_domain(None, declaration), [
            ("id", "=", self.env.company.id),
        ])

    def test_map_0100_accountant(self):
        """Register 0100 (mandatory) maps the accountant configured on 0000."""
        accountant = self.env["res.partner"].create(
            {"name": "Contador Y", "is_company": False, "district": "Centro"}
        )
        declaration = self.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {
                "company_id": self.env.company.id,
                "accountant_id": accountant.id,
                "accountant_crc": "SP-123456",
            }
        )
        reg = self.env["l10n_br_sped.efd_icms_ipi.0100"]
        vals = reg._map_from_odoo(accountant, declaration, declaration)
        self.assertEqual(vals["NOME"], "Contador Y")
        self.assertEqual(vals["CRC"], "SP-123456")
        self.assertEqual(vals["BAIRRO"], "Centro")

    def test_map_c100_document(self):
        """Register C100 (Bloco C) maps a fiscal document header."""
        partner = self.env["res.partner"].create(
            {"name": "Cliente C", "is_company": True}
        )
        document = self.env["l10n_br_fiscal.document"].new(
            {
                "partner_id": partner.id,
                "document_serie": "1",
                "document_number": "123",
            }
        )
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.c100"]._map_from_odoo(
            document, declaration, declaration
        )
        self.assertEqual(vals["COD_PART"], str(partner.id))
        self.assertEqual(vals["SER"], "1")
        self.assertEqual(vals["NUM_DOC"], "123")
        self.assertIn("VL_BC_ICMS", vals)

    def test_map_c170_line(self):
        """Register C170 maps a document line (item)."""
        product = self.env["product.product"].create(
            {"name": "Item", "default_code": "IT1"}
        )
        line = self.env["l10n_br_fiscal.document.line"].new(
            {"product_id": product.id, "name": "Item desc"}
        )
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.c170"]._map_from_odoo(
            line, None, declaration, index=4
        )
        self.assertEqual(vals["NUM_ITEM"], 5)
        self.assertEqual(vals["COD_ITEM"], "IT1")
        self.assertEqual(vals["CST_ICMS"], "000")
        self.assertEqual(vals["IND_APUR"], declaration.ind_apur)

    def test_map_c190_analytic(self):
        """Register C190 maps an analytical aggregation row."""
        declaration = self._declaration()
        row = {
            "cst_icms": "000",
            "cfop": "5102",
            "aliq_icms": 18.0,
            "vl_opr": 100.0,
            "vl_bc_icms": 100.0,
            "vl_icms": 18.0,
        }
        vals = self.env["l10n_br_sped.efd_icms_ipi.c190"]._map_from_odoo(
            row, None, declaration
        )
        self.assertEqual(vals["CST_ICMS"], "000")
        self.assertEqual(vals["CFOP"], "5102")
        self.assertEqual(vals["ALIQ_ICMS"], 18.0)
        self.assertEqual(vals["VL_ICMS"], 18.0)

    def test_map_e100_period(self):
        """Register E100 maps the ICMS assessment period from the declaration."""
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.e100"]._map_from_odoo(
            None, None, declaration
        )
        self.assertEqual(vals["DT_INI"], declaration.DT_INI)
        self.assertEqual(vals["DT_FIN"], declaration.DT_FIN)

    def test_map_e110_icms_assessment(self):
        """Register E110 computes the ICMS balance (debits vs credits)."""
        declaration = self._declaration()
        reg = self.env["l10n_br_sped.efd_icms_ipi.e110"]
        debtor = reg._map_from_odoo(
            {"vl_debitos": 1000.0, "vl_creditos": 300.0}, None, declaration
        )
        self.assertEqual(debtor["VL_TOT_DEBITOS"], 1000.0)
        self.assertEqual(debtor["VL_TOT_CREDITOS"], 300.0)
        self.assertEqual(debtor["VL_SLD_APURADO"], 700.0)
        self.assertEqual(debtor["VL_ICMS_RECOLHER"], 700.0)
        self.assertEqual(debtor["VL_SLD_CREDOR_TRANSPORTAR"], 0.0)
        creditor = reg._map_from_odoo(
            {"vl_debitos": 200.0, "vl_creditos": 500.0}, None, declaration
        )
        self.assertEqual(creditor["VL_SLD_APURADO"], 0.0)
        self.assertEqual(creditor["VL_ICMS_RECOLHER"], 0.0)
        self.assertEqual(creditor["VL_SLD_CREDOR_TRANSPORTAR"], 300.0)

    def test_map_e500_ipi_period(self):
        """Register E500 maps the IPI assessment period from the declaration."""
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.e500"]._map_from_odoo(
            None, None, declaration
        )
        self.assertEqual(vals["IND_APUR"], declaration.ind_apur)
        self.assertEqual(vals["DT_INI"], declaration.DT_INI)
        self.assertEqual(vals["DT_FIN"], declaration.DT_FIN)

    def test_map_e520_ipi_assessment(self):
        """Register E520 computes the IPI balance (debits vs credits)."""
        declaration = self._declaration()
        reg = self.env["l10n_br_sped.efd_icms_ipi.e520"]
        debtor = reg._map_from_odoo(
            {"vl_deb": 500.0, "vl_cred": 200.0}, None, declaration
        )
        self.assertEqual(debtor["VL_DEB_IPI"], 500.0)
        self.assertEqual(debtor["VL_CRED_IPI"], 200.0)
        self.assertEqual(debtor["VL_SD_IPI"], 300.0)
        self.assertEqual(debtor["VL_SC_IPI"], 0.0)
        creditor = reg._map_from_odoo(
            {"vl_deb": 100.0, "vl_cred": 400.0}, None, declaration
        )
        self.assertEqual(creditor["VL_SD_IPI"], 0.0)
        self.assertEqual(creditor["VL_SC_IPI"], 300.0)

    def test_map_k010_layout(self):
        """Register K010 maps the Bloco K layout type from the declaration."""
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.k010"]._map_from_odoo(
            None, None, declaration
        )
        self.assertEqual(vals["IND_TP_LEIAUTE"], declaration.ind_tp_leiaute)

    def test_map_k100_period(self):
        """Register K100 maps the stock/production period from the declaration."""
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.k100"]._map_from_odoo(
            None, None, declaration
        )
        self.assertEqual(vals["DT_INI"], declaration.DT_INI)
        self.assertEqual(vals["DT_FIN"], declaration.DT_FIN)

    def test_map_k200_stock(self):
        """Register K200 maps the end-of-period stock balance of an item."""
        product = self.env["product.product"].create(
            {"name": "Insumo", "default_code": "INS1", "type": "consu",
             "is_storable": True}
        )
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.k200"]._map_from_odoo(
            product, None, declaration
        )
        self.assertEqual(vals["COD_ITEM"], "INS1")
        self.assertEqual(vals["DT_EST"], declaration.DT_FIN)
        self.assertEqual(vals["IND_EST"], "0")
        self.assertIn("QTD", vals)

    def test_map_k230_production(self):
        """Register K230 maps a finished production order (mrp soft dependency)."""
        declaration = self._declaration()
        row = {"cod_doc_op": "MO/001", "cod_item": "PRD1", "qtd_enc": 10.0}
        vals = self.env["l10n_br_sped.efd_icms_ipi.k230"]._map_from_odoo(
            row, None, declaration
        )
        self.assertEqual(vals["COD_DOC_OP"], "MO/001")
        self.assertEqual(vals["COD_ITEM"], "PRD1")
        self.assertEqual(vals["QTD_ENC"], 10.0)

    def test_map_k235_consumption(self):
        """Register K235 maps a consumed raw-material move of a production."""
        declaration = self._declaration()
        row = {"cod_item": "INS-K", "qtd": 5.0}
        vals = self.env["l10n_br_sped.efd_icms_ipi.k235"]._map_from_odoo(
            row, {"id": 1}, declaration
        )
        self.assertEqual(vals["COD_ITEM"], "INS-K")
        self.assertEqual(vals["QTD"], 5.0)

    def test_k230_query_without_mrp(self):
        """K230 yields an empty query when mrp is not installed (soft dep)."""
        declaration = self._declaration()
        reg = self.env["l10n_br_sped.efd_icms_ipi.k230"]
        query, params = reg._odoo_query(None, declaration)
        if "mrp.production" not in self.env:
            self.assertIn("FALSE", query)
            self.assertEqual(params, [])

    def test_map_h005_inventory_totals(self):
        """Register H005 maps the period-end inventory totals (Bloco H)."""
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.h005"]._map_from_odoo(
            None, None, declaration
        )
        self.assertEqual(vals["DT_INV"], declaration.DT_FIN)
        self.assertEqual(vals["MOT_INV"], "01")
        self.assertIn("VL_INV", vals)

    def test_map_h010_inventory_item(self):
        """Register H010 maps an inventory item with quantity and cost."""
        product = self.env["product.product"].create(
            {"name": "Estoque", "default_code": "EST1", "type": "consu",
             "is_storable": True, "standard_price": 7.0}
        )
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.h010"]._map_from_odoo(
            product, None, declaration
        )
        self.assertEqual(vals["COD_ITEM"], "EST1")
        self.assertEqual(vals["VL_UNIT"], 7.0)
        self.assertEqual(vals["IND_PROP"], "0")

    def test_map_d100_cte(self):
        """Register D100 maps a transport document (CT-e)."""
        partner = self.env["res.partner"].create(
            {"name": "Transportadora", "is_company": True}
        )
        document = self.env["l10n_br_fiscal.document"].new(
            {"partner_id": partner.id, "document_serie": "1", "document_number": "55"}
        )
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.d100"]._map_from_odoo(
            document, declaration, declaration
        )
        self.assertEqual(vals["COD_PART"], str(partner.id))
        self.assertEqual(vals["SER"], "1")
        self.assertEqual(vals["NUM_DOC"], "55")
        self.assertIn("CHV_CTE", vals)

    def test_map_d190_analytic(self):
        """Register D190 maps a transport analytical aggregation row."""
        declaration = self._declaration()
        row = {"cst_icms": "000", "cfop": "1352", "aliq_icms": 12.0,
               "vl_opr": 50.0, "vl_bc_icms": 50.0, "vl_icms": 6.0}
        vals = self.env["l10n_br_sped.efd_icms_ipi.d190"]._map_from_odoo(
            row, None, declaration
        )
        self.assertEqual(vals["CST_ICMS"], "000")
        self.assertEqual(vals["CFOP"], "1352")
        self.assertEqual(vals["VL_ICMS"], 6.0)

    def test_map_c500_utility(self):
        """Register C500 maps an energy/water/gas utility document."""
        partner = self.env["res.partner"].create(
            {"name": "Concessionaria", "is_company": True}
        )
        document = self.env["l10n_br_fiscal.document"].new(
            {"partner_id": partner.id, "document_serie": "U", "document_number": "900"}
        )
        declaration = self._declaration()
        vals = self.env["l10n_br_sped.efd_icms_ipi.c500"]._map_from_odoo(
            document, declaration, declaration
        )
        self.assertEqual(vals["COD_PART"], str(partner.id))
        self.assertEqual(vals["NUM_DOC"], "900")
        self.assertIn("VL_FORN", vals)

    def test_map_c590_analytic(self):
        """Register C590 maps a utility analytical aggregation row."""
        declaration = self._declaration()
        row = {"cst_icms": "060", "cfop": "1252", "aliq_icms": 25.0,
               "vl_opr": 300.0, "vl_bc_icms": 0.0, "vl_icms": 0.0,
               "vl_bc_icms_st": 300.0, "vl_icms_st": 75.0}
        vals = self.env["l10n_br_sped.efd_icms_ipi.c590"]._map_from_odoo(
            row, None, declaration
        )
        self.assertEqual(vals["CST_ICMS"], "060")
        self.assertEqual(vals["CFOP"], "1252")
        self.assertEqual(vals["VL_ICMS_ST"], 75.0)

    # ------------------------------------------------------------------
    # End-to-end / round-trip
    # ------------------------------------------------------------------
    def test_generate_then_import_round_trip(self):
        """Generate a file, import it back, regenerate: must be identical.

        Validates the symmetry between the writer (_generate_sped_text) and
        the reader (_import_file): field order, line format and the control
        block (9900/9990/9999) must round-trip exactly.
        """
        declaration = self.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {"company_id": self.env.company.id}
        )
        # A few level-2 registers covering char fields.
        self.env["l10n_br_sped.efd_icms_ipi.0005"].create(
            {"declaration_id": declaration.id, "FANTASIA": "ACME", "BAIRRO": "Centro"}
        )
        self.env["l10n_br_sped.efd_icms_ipi.0190"].create(
            {"declaration_id": declaration.id, "UNID": "UN", "DESCR": "Unidade"}
        )
        sped_1 = declaration._generate_sped_text()

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False
        ) as tmp:
            tmp.write(sped_1)
            tmp_path = tmp.name

        imported = self.env["l10n_br_sped.mixin"]._import_file(
            tmp_path, "efd_icms_ipi"
        )
        sped_2 = imported._generate_sped_text()
        self.assertEqual(sped_1.strip(), sped_2.strip())

    def test_full_pipeline_headless(self):
        """Pull from Odoo and generate the file with no UI interaction.

        Exercises _odoo_domain/_odoo_query, recursive register creation and the
        whole file generation, and asserts the 0000 self-population fix.
        """
        declaration = self.env["l10n_br_sped.efd_icms_ipi.0000"].create(
            {"company_id": self.env.company.id, "CLAS_ESTAB_IND": "00"}
        )
        declaration.button_populate_sped_from_odoo()
        # 0000 self-fields populated by the pull (not only by the form onchange).
        self.assertEqual(declaration.COD_VER, "020")
        declaration.button_create_sped_files()
        attachment = self.env["ir.attachment"].search(
            [("res_model", "=", declaration._name), ("res_id", "=", declaration.id)],
            limit=1,
        )
        self.assertTrue(attachment)
        content = base64.b64decode(attachment.datas).decode()
        self.assertIn("|0000|", content)
        self.assertIn("|9999|", content)
        # COD_VER (020) must be on the 0000 line.
        opening = content.splitlines()[0]
        self.assertEqual(opening.split("|")[2], "020")
