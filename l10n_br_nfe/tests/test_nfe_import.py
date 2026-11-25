# Copyright 2021 - TODAY Akretion - Raphael Valyi <raphael.valyi@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import importlib.resources
import re

import nfelib
from nfelib.nfe.bindings.v4_0.leiaute_nfe_v4_00 import TnfeProc

from odoo.models import NewId
from odoo.tests import TransactionCase


class NFeImportTest(TransactionCase):
    def test_import_in_nfe_dry_run(self):
        res_items = (
            "nfe",
            "samples",
            "v4_0",
            "leiauteNFe",
            "35180834128745000152550010000474281920007498-nfe.xml",
        )

        binding = TnfeProc.from_xml(
            importlib.resources.files(nfelib.__name__)
            .joinpath(*res_items)
            .read_bytes()
            .decode()
        )
        nfe = self.env["l10n_br_fiscal.document"].import_binding_nfe(
            binding, edoc_type="in", dry_run=True
        )
        assert isinstance(nfe.id, NewId)
        self._check_nfe(nfe)

    def test_import_in_nfe(self):
        res_items = (
            "nfe",
            "samples",
            "v4_0",
            "leiauteNFe",
            "35180834128745000152550010000474281920007498-nfe.xml",
        )
        binding = TnfeProc.from_xml(
            importlib.resources.files(nfelib.__name__)
            .joinpath(*res_items)
            .read_bytes()
            .decode()
        )
        nfe = self.env["l10n_br_fiscal.document"].import_binding_nfe(
            binding, edoc_type="in", dry_run=False
        )

        assert isinstance(nfe.id, int)
        self._check_nfe(nfe)

    def test_items_without_gtin_do_not_all_match_the_same_product(self):
        res_items = (
            "nfe",
            "samples",
            "v4_0",
            "leiauteNFe",
            "35180834128745000152550010000474281920007498-nfe.xml",
        )
        resource_path = "/".join(res_items)
        nfe_stream = importlib.resources.files(nfelib.__name__).joinpath(resource_path)
        xml = nfe_stream.read_bytes().decode()
        xml = re.sub(r"<cEAN>[^<]*</cEAN>", "<cEAN>SEM GTIN</cEAN>", xml)
        xml = re.sub(
            r"<cEANTrib>[^<]*</cEANTrib>", "<cEANTrib>SEM GTIN</cEANTrib>", xml
        )

        binding = TnfeProc.from_xml(xml)
        nfe = self.env["l10n_br_fiscal.document"].import_binding_nfe(
            binding, edoc_type="in", dry_run=False
        )

        codes = [line.nfe40_cProd for line in nfe.fiscal_line_ids]
        self.assertEqual(len(set(codes)), len(codes))
        self.assertEqual(
            [line.product_id.default_code for line in nfe.fiscal_line_ids], codes
        )
        products = nfe.fiscal_line_ids.mapped("product_id")
        self.assertEqual(len(products), len(nfe.fiscal_line_ids))

    def test_import_nfe_autxml_dedup(self):
        """autXML "contato" partners are deduplicated by CNPJ.

        An inbound NFe carrying the same CNPJ in both ``<autXML>`` and
        ``<infRespTec>`` (typical: the software house is both the authorized
        XML downloader and the technical responsible) must import a single
        partner instead of raising the l10n_br_base CNPJ uniqueness
        constraint.

        Regression test: the ``_build_attr`` autXML shortcut MUST return
        after setting the deduplicated ``Command.set`` values, otherwise the
        generic o2m path overwrites them with ``Command.create`` entries and
        the same partners are created a second time at document create (a
        merge resolution once dropped that return and broke supplier NFe
        imports carrying an autXML section).
        """
        res_items = (
            "nfe",
            "samples",
            "v4_0",
            "leiauteNFe",
            "35180834128745000152550010000474281920007498-nfe.xml",
        )
        xml = (
            importlib.resources.files(nfelib.__name__)
            .joinpath(*res_items)
            .read_bytes()
            .decode()
        )

        # the sample has <infRespTec> with Akretion's CNPJ; use the same
        # fresh CNPJ for both <infRespTec> and a new <autXML> entry
        cnpj = "12345678000195"
        assert "<autXML>" not in xml
        xml = xml.replace("<CNPJ>11034414000158</CNPJ>", f"<CNPJ>{cnpj}</CNPJ>")
        xml = xml.replace("</infNFe>", f"<autXML><CNPJ>{cnpj}</CNPJ></autXML></infNFe>")
        binding = TnfeProc.from_xml(xml)

        before = self.env["res.partner"].search_count(
            [("cnpj_cpf_stripped", "=", cnpj)]
        )
        nfe = (
            self.env["l10n_br_fiscal.document"]
            .with_context(allow_product_creation=True)
            .import_binding_nfe(binding, edoc_type="in", dry_run=False)
        )
        after = self.env["res.partner"].search_count([("cnpj_cpf_stripped", "=", cnpj)])

        # exactly one "contato" partner for the autXML/infRespTec CNPJ
        self.assertEqual(after - before, 1)
        self.assertEqual(len(nfe.nfe40_autXML), 1)

    def _check_nfe(self, nfe):
        self.assertEqual(type(nfe)._name, "l10n_br_fiscal.document")
        self.assertEqual(
            nfe.document_type_id, self.env.ref("l10n_br_fiscal.document_55")
        )
        self.assertEqual(nfe.document_number, "47428")

        # here we check that emit and enderEmit
        # are now the supplier data (partner_id)
        self.assertEqual(nfe.partner_id.name, "Alimentos Saudaveis")
        # (CNPJ is not formated yet in dry run)
        self.assertTrue(nfe.partner_id.vat in ("34.128.745/0001-52", "34128745000152"))
        # this tests the _extract_related_values method for related values:
        self.assertEqual(nfe.partner_id.legal_name, "Alimentos Ltda.")

        # enderDest
        nfe.partner_id._inverse_nfe40_CEP()
        self.assertEqual(nfe.partner_id.street_name, "Rua Fonseca")  # related xLgr
        self.assertEqual(nfe.partner_id.zip, "13877-123")
        self.assertEqual(nfe.partner_id.nfe40_CEP, "13877123")
        self.assertEqual(nfe.partner_id.city_id.name, "São João da Boa Vista")

        # now we check that company_id is unchanged
        self.assertEqual(nfe.company_id, self.env.ref("base.main_company"))

        # this tests that value is not overrident by stacked default vals
        self.assertEqual(nfe.nfe40_modFrete, "0")  # (default is 9)

        # lines data
        self.assertEqual(len(nfe.fiscal_line_ids), 6)
        self.assertEqual(nfe.fiscal_line_ids[0].quantity, 6)
        # NOTE / FIXME price unit is rounded to 7.16 if create and 7.155 if dry run
        self.assertTrue(abs(nfe.fiscal_line_ids[0].price_unit - 7.16) < 0.01)
        self.assertTrue(abs(nfe.fiscal_line_ids[0].fiscal_price - 7.16) < 0.01)

        # impostos
        self.assertEqual(nfe.fiscal_line_ids[0].icms_base_type, "0")
        self.assertEqual(nfe.fiscal_line_ids[0].icms_cst_id.code, "00")
        self.assertEqual(nfe.fiscal_line_ids[0].icms_base, 50.60)
        self.assertEqual(nfe.fiscal_line_ids[0].icms_value, 6.07)
        self.assertEqual(nfe.fiscal_line_ids[0].ipi_value, 0)

        # products
        self.assertEqual(nfe.fiscal_line_ids[0].nfe40_nItem, "1")
        self.assertEqual(nfe.fiscal_line_ids[0].product_id.name, "QUINOA 100G (2X50G)")
        self.assertEqual(nfe.fiscal_line_ids[0].product_id.barcode, "7897846902086")
        self.assertEqual(
            nfe.fiscal_line_ids[0].product_id.ncm_id.name[0:14], "Trigo mourisco"
        )
        self.assertEqual(nfe.fiscal_line_ids[0].product_id.ncm_id.code, "1008.50.90")

        self.assertEqual(
            nfe.fiscal_line_ids[1].product_id.name, "QUINOA VEGETAIS 100G (2X50G)"
        )
        self.assertEqual(
            nfe.fiscal_line_ids[2].product_id.name, "QUINOA PICANTE 100G (2X50G)"
        )

    def test_import_in_nfe_delivery_address(self):
        """A purchase NFe with an <entrega> block must import the delivery
        address into the stored partner_shipping_id (nfe40_entrega is a
        non-stored computed field, so it cannot hold the imported value)."""
        res_items = (
            "nfe",
            "samples",
            "v4_0",
            "leiauteNFe",
            "35180834128745000152550010000474281920007498-nfe.xml",
        )
        xml = (
            importlib.resources.files(nfelib.__name__)
            .joinpath(*res_items)
            .read_bytes()
            .decode()
        )
        entrega = (
            "<entrega>"
            "<CNPJ>34128745000152</CNPJ>"
            "<xLgr>Rua da Entrega</xLgr><nro>999</nro><xBairro>Centro</xBairro>"
            "<cMun>3550308</cMun><xMun>SAO PAULO</xMun><UF>SP</UF>"
            "<CEP>01001000</CEP><cPais>1058</cPais><xPais>Brasil</xPais>"
            "</entrega>"
        )
        xml = xml.replace("</dest>", "</dest>" + entrega, 1)
        binding = TnfeProc.from_xml(xml)
        nfe = self.env["l10n_br_fiscal.document"].import_binding_nfe(
            binding, edoc_type="in", dry_run=False
        )
        shipping = nfe.partner_shipping_id
        self.assertTrue(shipping, "delivery address was not imported")
        self.assertNotEqual(shipping, nfe.partner_id)
        self.assertEqual(shipping.type, "delivery")
        self.assertEqual(shipping.street_name, "Rua da Entrega")
        self.assertEqual(shipping.zip, "01001-000")

    def test_import_in_nfe_creates_reduced_tax(self):
        """A purchase NFe line declaring an ICMS base reduction (CST 20 with
        pRedBC) for which the company has no matching fiscal tax must create a
        tax carrying that percent_reduction, instead of falling back to a
        plain no-reduction tax (which would compute a wrong ICMS credit)."""
        res_items = (
            "nfe",
            "samples",
            "v4_0",
            "leiauteNFe",
            "35180834128745000152550010000474281920007498-nfe.xml",
        )
        xml = (
            importlib.resources.files(nfelib.__name__)
            .joinpath(*res_items)
            .read_bytes()
            .decode()
        )
        # Replace the first ICMS00 node with an ICMS20 (base reduction).
        # pICMS 7.00 + 33.33% reduction is unlikely to pre-exist -> forces
        # the create-if-not-found branch.
        icms20 = (
            "<ICMS20>"
            "<orig>0</orig><CST>20</CST><modBC>3</modBC>"
            "<pRedBC>33.33</pRedBC><vBC>33.73</vBC>"
            "<pICMS>7.00</pICMS><vICMS>2.36</vICMS>"
            "</ICMS20>"
        )
        xml = re.sub(r"<ICMS00>.*?</ICMS00>", icms20, xml, count=1, flags=re.S)

        existing = self.env["l10n_br_fiscal.tax"].search(
            [
                ("tax_group_id", "=", self.env.ref("l10n_br_fiscal.tax_group_icms").id),
                ("percent_amount", "=", 7.0),
                ("percent_reduction", "=", 33.33),
            ]
        )
        self.assertFalse(existing, "test precondition: reduced tax must not exist")

        binding = TnfeProc.from_xml(xml)
        nfe = self.env["l10n_br_fiscal.document"].import_binding_nfe(
            binding, edoc_type="in", dry_run=False
        )
        created = self.env["l10n_br_fiscal.tax"].search(
            [
                ("tax_group_id", "=", self.env.ref("l10n_br_fiscal.tax_group_icms").id),
                ("percent_amount", "=", 7.0),
                ("percent_reduction", "=", 33.33),
            ]
        )
        self.assertTrue(created, "reduced ICMS tax was not created on import")
        line = nfe.fiscal_line_ids[0]
        self.assertEqual(line.icms_tax_id, created)
        self.assertEqual(line.icms_tax_id.percent_reduction, 33.33)

    def _sample_xml(self):
        res_items = (
            "nfe",
            "samples",
            "v4_0",
            "leiauteNFe",
            "35180834128745000152550010000474281920007498-nfe.xml",
        )
        return (
            importlib.resources.files(nfelib.__name__)
            .joinpath(*res_items)
            .read_bytes()
            .decode()
        )

    def test_import_out_nfe(self):
        "(can be useful after an ERP migration)"
        binding = TnfeProc.from_xml(self._sample_xml())
        nfe = self.env["l10n_br_fiscal.document"].import_binding_nfe(
            binding, edoc_type="out", dry_run=True
        )
        self.assertTrue(nfe.partner_id)
        self.assertEqual(nfe.partner_id.vat, "68161525650")

    def test_import_out_nfe_of_a_recipient_abroad(self):
        """An export NF-e: the recipient abroad carries idEstrangeiro instead of
        CNPJ or CPF, and its address follows the MOC convention for abroad."""
        xml = self._sample_xml()
        dest_abroad = """<dest>
        <idEstrangeiro>123456789</idEstrangeiro>
        <xNome>ACME IMPORTS LLC</xNome>
        <enderDest>
          <xLgr>MAIN STREET</xLgr>
          <nro>100</nro>
          <xBairro>EX</xBairro>
          <cMun>9999999</cMun>
          <xMun>EXTERIOR</xMun>
          <UF>EX</UF>
          <cPais>2496</cPais>
          <xPais>ESTADOS UNIDOS</xPais>
        </enderDest>
        <indIEDest>9</indIEDest>
      </dest>"""
        xml = re.sub(r"<dest>.*?</dest>", dest_abroad, xml, count=1, flags=re.S)
        xml = re.sub(r"<idDest>\d</idDest>", "<idDest>3</idDest>", xml, count=1)
        self.assertNotIn("<CPF>", xml[xml.index("<dest>") : xml.index("</dest>")])

        binding = TnfeProc.from_xml(xml)
        nfe = self.env["l10n_br_fiscal.document"].import_binding_nfe(
            binding, edoc_type="out", dry_run=True
        )
        self.assertTrue(nfe.partner_id)
        self.assertEqual(nfe.partner_id.legal_name, "ACME IMPORTS LLC")
        self.assertFalse(nfe.partner_id.vat)

    def test_import_in_nfe_ipi_reaches_the_totals(self):
        res_items = (
            "nfe",
            "samples",
            "v4_0",
            "leiauteNFe",
            "35180834128745000152550010000474281920007498-nfe.xml",
        )
        xml = (
            importlib.resources.files(nfelib.__name__)
            .joinpath(*res_items)
            .read_bytes()
            .decode()
        )
        ipi = (
            "<IPI><cEnq>999</cEnq><IPITrib>"
            "<CST>50</CST><vBC>50.60</vBC><pIPI>6.50</pIPI><vIPI>3.29</vIPI>"
            "</IPITrib></IPI>"
        )
        xml = re.sub(r"<IPI>.*?</IPI>", ipi, xml, count=1, flags=re.S)

        binding = TnfeProc.from_xml(xml)
        nfe = self.env["l10n_br_fiscal.document"].import_binding_nfe(
            binding, edoc_type="in", dry_run=False
        )
        line = nfe.fiscal_line_ids[0]
        self.assertAlmostEqual(line.ipi_value, 3.29, places=2)
        self.assertAlmostEqual(line.amount_tax_not_included, 3.29, places=2)
        self.assertAlmostEqual(line.fiscal_amount_tax, 3.29, places=2)
        self.assertAlmostEqual(line.amount_tax_included, 7.64, places=2)

    def _import_first_line_with_icms(self, icms_xml):
        xml = re.sub(
            r"<ICMS00>.*?</ICMS00>", icms_xml, self._sample_xml(), count=1, flags=re.S
        )
        # The sample item also carries an ICMSUFDest (DIFAL), which has its own FCP
        # and would overwrite the FCP of the ICMS group: a purchase from a
        # taxpayer has none.
        xml = re.sub(r"<ICMSUFDest>.*?</ICMSUFDest>", "", xml, count=1, flags=re.S)
        binding = TnfeProc.from_xml(xml)
        nfe = self.env["l10n_br_fiscal.document"].import_binding_nfe(
            binding, edoc_type="in", dry_run=False
        )
        return nfe.fiscal_line_ids[0]

    def test_import_in_nfe_icms_st_and_fcp_st(self):
        # ICMS10: ICMS 18%, FCP 2%, ICMS ST (MVA 40%) and FCP ST 2%
        line = self._import_first_line_with_icms(
            "<ICMS10>"
            "<orig>0</orig><CST>10</CST><modBC>3</modBC>"
            "<vBC>100.00</vBC><pICMS>18.00</pICMS><vICMS>18.00</vICMS>"
            "<vBCFCP>100.00</vBCFCP><pFCP>2.00</pFCP><vFCP>2.00</vFCP>"
            "<modBCST>4</modBCST><pMVAST>40.00</pMVAST>"
            "<vBCST>140.00</vBCST><pICMSST>18.00</pICMSST><vICMSST>7.20</vICMSST>"
            "<vBCFCPST>140.00</vBCFCPST><pFCPST>2.00</pFCPST>"
            "<vFCPST>2.80</vFCPST>"
            "</ICMS10>"
        )

        self.assertEqual(line.icmsst_base, 140.0)
        self.assertEqual(line.icmsst_percent, 18.0)
        self.assertEqual(line.icmsst_value, 7.2)
        self.assertEqual(
            line.icmsst_tax_id, self.env.ref("l10n_br_fiscal.tax_icmsst_40")
        )
        self.assertEqual(line.icmsfcp_base, 100.0)
        self.assertEqual(line.icmsfcp_percent, 2.0)
        self.assertEqual(line.icmsfcp_value, 2.0)
        self.assertEqual(
            line.icmsfcp_tax_id, self.env.ref("l10n_br_fiscal.tax_icmsfcp_2")
        )
        self.assertEqual(line.icmsfcpst_base, 140.0)
        self.assertEqual(line.icmsfcpst_percent, 2.0)
        self.assertEqual(line.icmsfcpst_value, 2.8)
        self.assertEqual(
            line.icmsfcpst_tax_id, self.env.ref("l10n_br_fiscal.tax_icmsfcp_st_2")
        )

    def test_import_in_nfe_icms00_fcp(self):
        # ICMS00 has pFCP/vFCP but no vBCFCP: the FCP base is the ICMS base
        line = self._import_first_line_with_icms(
            "<ICMS00>"
            "<orig>0</orig><CST>00</CST><modBC>3</modBC>"
            "<vBC>100.00</vBC><pICMS>18.00</pICMS><vICMS>18.00</vICMS>"
            "<pFCP>2.00</pFCP><vFCP>2.00</vFCP>"
            "</ICMS00>"
        )

        self.assertEqual(line.icmsfcp_base, 100.0)
        self.assertEqual(line.icmsfcp_percent, 2.0)
        self.assertEqual(line.icmsfcp_value, 2.0)
        self.assertEqual(
            line.icmsfcp_tax_id, self.env.ref("l10n_br_fiscal.tax_icmsfcp_2")
        )
        self.assertFalse(line.icmsst_tax_id)
        self.assertFalse(line.icmsfcpst_tax_id)

    def test_import_in_nfe_icms_st_rate_without_tax_keeps_the_amounts(self):
        line = self._import_first_line_with_icms(
            "<ICMS10>"
            "<orig>0</orig><CST>10</CST><modBC>3</modBC>"
            "<vBC>100.00</vBC><pICMS>18.00</pICMS><vICMS>18.00</vICMS>"
            "<modBCST>4</modBCST><pMVAST>40.00</pMVAST>"
            "<vBCST>140.00</vBCST><pICMSST>17.50</pICMSST><vICMSST>6.50</vICMSST>"
            "<vBCFCPST>140.00</vBCFCPST><pFCPST>3.50</pFCPST>"
            "<vFCPST>4.90</vFCPST>"
            "</ICMS10>"
        )

        self.assertEqual(line.icmsst_value, 6.5)
        self.assertEqual(line.icmsfcpst_value, 4.9)
        self.assertFalse(line.icmsst_tax_id)
        self.assertEqual(
            line.icmsfcpst_tax_id, self.env.ref("l10n_br_fiscal.tax_icmsfcp_st_nt")
        )
