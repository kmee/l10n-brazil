# Copyright 2021 - TODAY Akretion - Raphael Valyi <raphael.valyi@akretion.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import importlib.resources
import io
import os
import re
import zipfile
from datetime import date

import nfelib
from nfelib.nfe.bindings.v4_0.leiaute_nfe_v4_00 import TnfeProc

from odoo.models import NewId
from odoo.tests import TransactionCase

from odoo.addons import l10n_br_nfe
from odoo.addons.l10n_br_fiscal_edi.tests.common import (
    KEY_1,
    KEY_2,
    KEY_3,
    EdiImportCase,
)
from odoo.addons.l10n_br_fiscal_edi.tools import EdiInstallment, EdiPayment

FIXTURE_DIR = os.path.join(
    l10n_br_nfe.__path__[0], "tests", "nfe", "v4_00", "leiauteNFe"
)
FIXTURE_DEST = re.compile(rb"(<dest>\s*)<(?:CNPJ|CPF)>\d+</(?:CNPJ|CPF)>")
NFE_NS = "http://www.portalfiscal.inf.br/nfe"


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

    def test_items_without_gtin_do_not_all_match_the_same_product(self):
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
        self.assertTrue(
            nfe.partner_id.cnpj_cpf in ("34.128.745/0001-52", "34128745000152")
        )
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

    def test_import_out_nfe(self):
        "(can be useful after an ERP migration)"

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

    def _sample_nfe_xml(self):
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

    def test_import_out_nfe_foreign_recipient(self):
        """An outbound NFe to a foreign recipient (export) identifies the
        recipient only by idEstrangeiro: the import must not require a
        CNPJ/CPF (it used to fail with an unbound dest_vat)."""
        foreign_dest = (
            "<dest>"
            "<idEstrangeiro>US123456789</idEstrangeiro>"
            "<xNome>FOREIGN AVIATION BUYER INC</xNome>"
            "<enderDest>"
            "<xLgr>MAIN STREET</xLgr><nro>100</nro><xBairro>DOWNTOWN</xBairro>"
            "<cMun>9999999</cMun><xMun>EXTERIOR</xMun><UF>EX</UF>"
            "<cPais>2496</cPais><xPais>ESTADOS UNIDOS</xPais>"
            "</enderDest>"
            "<indIEDest>9</indIEDest>"
            "</dest>"
        )
        xml = re.sub(
            r"<dest>.*?</dest>",
            foreign_dest,
            self._sample_nfe_xml(),
            count=1,
            flags=re.S,
        )
        binding = TnfeProc.from_xml(xml)
        nfe = self.env["l10n_br_fiscal.document"].import_binding_nfe(
            binding, edoc_type="out", dry_run=False
        )
        self.assertEqual(nfe.partner_id.name, "FOREIGN AVIATION BUYER INC")
        self.assertFalse(nfe.partner_id.vat)

    def test_import_in_nfe_reduced_tax_other_cst(self):
        """The reduced ICMS tax created on import is looked up by rate,
        reduction AND CST, so its name must carry the CST: when a tax with
        the same rate and reduction already exists for another CST, the new
        one must not clash on the unique tax name."""
        icms_group = self.env.ref("l10n_br_fiscal.tax_group_icms")
        cst_70 = self.env["l10n_br_fiscal.cst"].search(
            [("code", "=", "70"), ("tax_domain", "=", "icms")], limit=1
        )
        self.env["l10n_br_fiscal.tax"].create(
            {
                "name": "ICMS 7.0% Com Red. 33.33%",
                "tax_group_id": icms_group.id,
                "percent_amount": 7.0,
                "percent_reduction": 33.33,
                "percent_debit_credit": 0,
                "value_amount": 0,
                "icmsst_mva_percent": 0,
                "icmsst_value": 0,
                "cst_in_id": cst_70.id,
                "cst_out_id": cst_70.id,
            }
        )
        icms20 = (
            "<ICMS20>"
            "<orig>0</orig><CST>20</CST><modBC>3</modBC>"
            "<pRedBC>33.33</pRedBC><vBC>33.73</vBC>"
            "<pICMS>7.00</pICMS><vICMS>2.36</vICMS>"
            "</ICMS20>"
        )
        xml = re.sub(
            r"<ICMS00>.*?</ICMS00>", icms20, self._sample_nfe_xml(), count=1, flags=re.S
        )
        binding = TnfeProc.from_xml(xml)
        nfe = self.env["l10n_br_fiscal.document"].import_binding_nfe(
            binding, edoc_type="in", dry_run=False
        )
        tax = nfe.fiscal_line_ids[0].icms_tax_id
        self.assertEqual(tax.percent_reduction, 33.33)
        self.assertEqual(tax.cst_in_id.code, "20")
        self.assertEqual(tax.name, "ICMS 7.0% Com Red. 33.33% CST 20")


class TestNfeDocumentImport(EdiImportCase):
    """The NF-e reader of the document import, on the XML files of the module."""

    @classmethod
    def _xml(cls, key, recipient=None, product="Brand new thing", replace=()):
        with open(os.path.join(FIXTURE_DIR, f"NFe{key}.xml"), "rb") as xml_file:
            content = xml_file.read()
        recipient = recipient or cls.company.partner_id.cnpj_cpf_stripped
        content = FIXTURE_DEST.sub(rb"\1<CNPJ>%s</CNPJ>" % recipient.encode(), content)
        content = content.replace(b"Cabinet with Doors", product.encode())
        content = content.replace(b"E-COM11", b"ZZ-NEW-1")
        for old, new in replace:
            content = content.replace(old, new)
        return content

    def _import(self, xml, name="nfe.xml", model=None):
        return (self.Document if model is None else model)._edi_import_files(
            [(name, xml)]
        )

    def _imported(self, xml, **kwargs):
        documents, errors, _warnings = self._import(xml, **kwargs)
        self.assertFalse(errors)
        return documents

    def _protocol(self, status):
        xml = self._xml(KEY_1).decode().split("?>", 1)[1]
        protocol = (
            f'<protNFe versao="4.00"><infProt><chNFe>{KEY_1}</chNFe>'
            f"<cStat>{status}</cStat></infProt></protNFe>"
        )
        xml = xml.replace("</NFe>", "</NFe>" + protocol)
        return f'<nfeProc xmlns="{NFE_NS}" versao="4.00">{xml}</nfeProc>'.encode()

    def test_xml_becomes_a_draft_document_without_creating_products(self):
        products = self.env["product.product"].search_count([])
        xml = self._xml(KEY_1)

        documents = self._imported(xml)

        self.assertEqual(documents.state_edoc, "em_digitacao")
        self.assertEqual(documents.company_id, self.company)
        self.assertEqual(documents.document_key, KEY_1)
        self.assertEqual(documents.import_state, "pending")
        self.assertEqual(documents.original_xml_file_id.raw, xml)
        line = documents.fiscal_line_ids
        self.assertEqual(line.name, "Brand new thing")
        self.assertEqual((line.quantity, line.price_unit), (1, 140))
        self.assertFalse(line.product_id)
        self.assertEqual(self.env["product.product"].search_count([]), products)

    def test_the_same_file_again_opens_the_same_document_with_a_warning(self):
        first = self._imported(self._xml(KEY_1))

        second, errors, warnings = self._import(self._xml(KEY_1))

        self.assertFalse(errors)
        self.assertEqual(first, second)
        self.assertEqual(len(warnings), 1)

    def test_zip_with_two_notes_and_an_invalid_file(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("one.xml", self._xml(KEY_1))
            archive.writestr("two.xml", self._xml(KEY_2))
            archive.writestr("bad.xml", b"this is not an XML")

        documents, errors, _warnings = self._import(buffer.getvalue(), "batch.zip")

        self.assertEqual(len(documents), 2)
        self.assertEqual([name for name, _message in errors], ["batch.zip/bad.xml"])

    def test_cancelled_denied_or_not_authorized_by_the_protocol_is_refused(self):
        for status in ("101", "110", "217"):
            documents, errors, _warnings = self._import(self._protocol(status))
            self.assertFalse(documents, status)
            self.assertEqual(len(errors), 1, status)
        self.assertEqual(len(self._imported(self._protocol("100"))), 1)

    def test_a_note_that_is_not_an_nfe_of_model_55_is_refused(self):
        xml = self._xml(KEY_1).replace(b"<mod>55</mod>", b"<mod>65</mod>")

        documents, errors, _warnings = self._import(xml)

        self.assertFalse(documents)
        self.assertIn("model 55", errors[0][1])

    def test_recipient_that_is_not_a_company_of_the_database_is_refused(self):
        xml = self._xml(KEY_1, recipient="11222333000181")

        documents, errors, _warnings = self._import(xml)

        self.assertFalse(documents)
        self.assertEqual(len(errors), 1)

    def test_note_goes_to_the_company_of_the_recipient(self):
        vat = self.other_company.partner_id.cnpj_cpf_stripped

        documents = self._imported(self._xml(KEY_1, recipient=vat))

        self.assertEqual(documents.company_id, self.other_company)

    def test_note_issued_by_the_company_is_imported_as_an_outbound_document(self):
        issuer = self.env.ref("l10n_br_base.empresa_lucro_presumido")
        xml = self._xml(KEY_3, recipient="11222333000181")

        documents = self._imported(xml)

        self.assertEqual(documents.company_id, issuer)
        self.assertEqual(documents.issuer, "company")
        self.assertEqual(documents.fiscal_operation_type, "out")
        self.assertNotEqual(documents.partner_id, issuer.partner_id)

    def test_total_of_the_item_is_the_one_declared_in_the_file(self):
        xml = self._xml(
            KEY_1,
            replace=[
                (b"<qCom>1.0000</qCom>", b"<qCom>3.0000</qCom>"),
                (b"<qTrib>1.0000</qTrib>", b"<qTrib>3.0000</qTrib>"),
                (b"<vUnCom>140.0000000000", b"<vUnCom>0.3350000000"),
                (b"<vUnTrib>140.0000000000", b"<vUnTrib>0.3350000000"),
                (b"<vProd>140.00</vProd>", b"<vProd>1.00</vProd>"),
            ],
        )

        line = self._imported(xml).fiscal_line_ids

        self.assertEqual(line.partner_price_gross, 1.0)
        self.assertEqual(line.price_gross, 1.0)

    def test_unknown_ncm_is_kept_as_declared_and_not_created(self):
        ncm = self.env["l10n_br_fiscal.ncm"].search_count([])
        xml = self._xml(
            KEY_1, replace=[(b"<NCM>94033000</NCM>", b"<NCM>99999999</NCM>")]
        )

        documents = self._imported(xml)

        line = documents.fiscal_line_ids
        self.assertEqual(line.partner_ncm_code, "99999999")
        self.assertFalse(line.ncm_id)
        self.assertIn("99999999", documents.import_warning)
        self.assertEqual(self.env["l10n_br_fiscal.ncm"].search_count([]), ncm)

    def test_matching_a_product_without_ncm_keeps_the_ncm_of_the_file(self):
        self.env["product.product"].create(
            {"name": "No NCM", "default_code": "ZZ-NEW-1", "ncm_id": False}
        )
        ncm = self.env["l10n_br_fiscal.ncm"].search(
            [("code_unmasked", "=", "94033000")], limit=1
        )

        documents = self._imported(self._xml(KEY_1))

        line = documents.fiscal_line_ids
        self.assertTrue(line.product_id)
        self.assertEqual(line.ncm_id, ncm)
        self.assertNotIn("NCM", documents.import_warning or "")

    def test_unknown_registries_are_not_created(self):
        models = ("l10n_br_fiscal.cest", "uom.uom", "res.city", "res.country")
        counts = [self.env[model].search_count([]) for model in models]
        xml = self._xml(
            KEY_1,
            replace=[
                (b"<NCM>94033000</NCM>", b"<NCM>94033000</NCM><CEST>9999999</CEST>"),
                (b"<uCom>UN</uCom>", b"<uCom>ZZZ</uCom>"),
                (b"<cMun>3501152</cMun>", b"<cMun>9999999</cMun>"),
            ],
        )

        self.assertTrue(self._imported(xml))

        self.assertEqual(counts, [self.env[model].search_count([]) for model in models])

    def test_unknown_cfop_is_not_created_and_does_not_break_the_import(self):
        cfop = self.env["l10n_br_fiscal.cfop"].search_count([])
        xml = self._xml(KEY_1, replace=[(b"<CFOP>5102</CFOP>", b"<CFOP>5999</CFOP>")])

        documents = self._imported(xml)

        self.assertFalse(documents.fiscal_operation_id)
        self.assertIn("fiscal operation", documents.import_warning)
        self.assertEqual(self.env["l10n_br_fiscal.cfop"].search_count([]), cfop)

    def test_operation_is_suggested_without_touching_the_values_of_the_file(self):
        documents = self._imported(self._xml(KEY_1))

        line = documents.fiscal_line_ids
        operation = self.env.ref("l10n_br_fiscal.fo_compras")
        self.assertEqual(documents.fiscal_operation_id, operation)
        self.assertEqual(line.fiscal_operation_id, operation)
        self.assertEqual(line.cfop_id.code, "1102")
        self.assertEqual(line.partner_cfop_id.code, "5102")
        self.assertEqual((line.quantity, line.price_unit), (1, 140))
        self.assertEqual(documents.fiscal_amount_total, 140)
        self.assertIs(documents.import_warning, False)

    def test_unknown_unit_stays_empty_and_is_kept_as_declared(self):
        uom = self.env["uom.uom"].search_count([])

        documents = self._imported(
            self._xml(KEY_1, replace=[(b"<uCom>UN</uCom>", b"<uCom>ZZZ</uCom>")])
        )

        line = documents.fiscal_line_ids
        self.assertFalse(line.uom_id)
        self.assertEqual(line.partner_uom_code, "ZZZ")
        self.assertEqual(line.import_state, "pending")
        self.assertIn("ZZZ", documents.import_warning)
        self.assertEqual(self.env["uom.uom"].search_count([]), uom)

    def test_known_unit_is_matched_not_defaulted(self):
        kilo = self.env["uom.uom"]._match_by_fiscal_code("KG")
        xml = self._xml(
            KEY_1,
            replace=[
                (b"<uCom>UN</uCom>", b"<uCom>KG</uCom>"),
                (b"<uTrib>UN</uTrib>", b"<uTrib>KG</uTrib>"),
            ],
        )

        documents = self._imported(xml)

        self.assertEqual(documents.fiscal_line_ids.uom_id, kilo)
        self.assertEqual(documents.fiscal_line_ids.uot_id, kilo)

    def test_matched_product_with_an_unknown_unit_still_awaits_review(self):
        xml = self._xml(
            KEY_1,
            replace=[
                (b"ZZ-NEW-1", b"E-COM11"),
                (b"<uCom>UN</uCom>", b"<uCom>ZZZ</uCom>"),
            ],
        )

        line = self._imported(xml).fiscal_line_ids

        self.assertTrue(line.product_id)
        self.assertEqual(line.import_state, "pending")

    def test_product_is_suggested_by_the_barcode_of_the_commercial_unit(self):
        product = self.env["product.product"].create(
            {"name": "Barcode only", "barcode": "7891234567895"}
        )
        xml = self._xml(
            KEY_1,
            replace=[
                (b"ZZ-NEW-1", b"OTHER-CODE"),
                (b"Brand new thing", b"Odd name"),
                (b"<cEAN>SEM GTIN</cEAN>", b"<cEAN>7891234567895</cEAN>"),
            ],
        )

        line = self._imported(xml).fiscal_line_ids

        self.assertEqual(line.product_id, product)
        self.assertEqual(line.import_state, "matched")

    def test_product_is_suggested_by_the_barcode_of_the_taxable_unit(self):
        product = self.env["product.product"].create(
            {"name": "Barcode only", "barcode": "7891234567895"}
        )
        xml = self._xml(
            KEY_1,
            replace=[
                (b"ZZ-NEW-1", b"OTHER-CODE"),
                (b"Brand new thing", b"Odd name"),
                (
                    b"<cEANTrib>SEM GTIN</cEANTrib>",
                    b"<cEANTrib>7891234567895</cEANTrib>",
                ),
            ],
        )

        line = self._imported(xml).fiscal_line_ids

        self.assertEqual(line.product_id, product)

    def test_the_barcode_of_the_file_never_creates_a_product(self):
        products = self.env["product.product"].search_count([])
        xml = self._xml(
            KEY_1,
            replace=[(b"<cEAN>SEM GTIN</cEAN>", b"<cEAN>7891234567895</cEAN>")],
        )

        line = self._imported(xml).fiscal_line_ids

        self.assertFalse(line.product_id)
        self.assertEqual(self.env["product.product"].search_count([]), products)

    # The de-para of the supplier: what a person decided on a note answers the next.

    def _depara_note(self, key, unit=b"UN", code=b"ZZ-NEW-1"):
        xml = self._xml(key)
        xml = re.sub(rb"<xProd>[^<]*</xProd>", b"<xProd>Odd name</xProd>", xml)
        xml = re.sub(rb"<cProd>[^<]*</cProd>", b"<cProd>%s</cProd>" % code, xml)
        xml = re.sub(rb"<uCom>[^<]*</uCom>", b"<uCom>%s</uCom>" % unit, xml)
        return re.sub(rb"<uTrib>[^<]*</uTrib>", b"<uTrib>%s</uTrib>" % unit, xml)

    def _supplier_product(self, uom=None, **info):
        uom = uom or self.uom_unit
        product = self.env["product.product"].create(
            {"name": "Mapped product", "uom_id": uom.id, "uom_po_id": uom.id}
        )
        issuers = self.env["res.partner"].search(
            [
                "|",
                ("cnpj_cpf_stripped", "=", "81583054000129"),
                ("vat", "=", "81.583.054/0001-29"),
            ]
        )
        for issuer in issuers:
            vals = {
                "partner_id": issuer.id,
                "product_id": product.id,
                "product_code": "ZZ-NEW-1",
                "price": 1,
            }
            vals.update(info)
            self.env["product.supplierinfo"].create(vals)
        return product

    def _dozen_note(self, code=b"ZZ-NEW-1"):
        """10 boxes at 35.00 (vProd 350.00)."""
        return (
            self._depara_note(KEY_2, unit=b"CX", code=code)
            .replace(b"<qCom>1.0000</qCom>", b"<qCom>10.0000</qCom>")
            .replace(b"<qTrib>1.0000</qTrib>", b"<qTrib>10.0000</qTrib>")
            .replace(
                b"<vUnCom>1950.0000000000</vUnCom>", b"<vUnCom>35.0000000000</vUnCom>"
            )
            .replace(
                b"<vUnTrib>1950.0000000000</vUnTrib>",
                b"<vUnTrib>35.0000000000</vUnTrib>",
            )
            .replace(b"<vProd>1950.00</vProd>", b"<vProd>350.00</vProd>")
        )

    def test_product_mapped_for_the_same_supplier_enters_resolved(self):
        product = self._supplier_product()

        line = self._imported(self._depara_note(KEY_2)).fiscal_line_ids

        self.assertEqual(line.product_id, product)
        self.assertEqual(line.import_state, "resolved")

    def test_unknown_unit_with_a_product_mapped_by_the_supplier_awaits_review(self):
        product = self._supplier_product()

        documents = self._imported(self._depara_note(KEY_2, unit=b"XPTO"))

        line = documents.fiscal_line_ids
        self.assertEqual(line.product_id, product)
        self.assertEqual(line.import_state, "pending")
        self.assertIn("XPTO", documents.import_warning)
        line.import_state = "matched"
        result = documents.action_import_confirm_suggestions()
        self.assertEqual(line.import_state, "matched")
        self.assertIn("1 line", result["params"]["message"])

    def test_total_of_the_file_holds_with_a_factor_from_the_de_para(self):
        box = self.env["uom.uom"]._match_by_fiscal_code("CX")
        product = self._supplier_product(partner_uom_id=box.id, partner_uom_factor=12)

        documents = self._imported(self._dozen_note())

        line = documents.fiscal_line_ids
        self.assertEqual(line.product_id, product)
        self.assertEqual(line.quantity, 120)
        self.assertEqual(line.import_state, "resolved")
        self.assertEqual(line.fiscal_amount_untaxed, 350)
        self.assertEqual(documents.fiscal_amount_untaxed, 350)

    def test_total_of_the_file_holds_when_a_person_resolves_with_a_factor(self):
        documents = self._imported(self._dozen_note(code=b"NO-MATCH-4"))
        product = self.env["product.product"].create({"name": "Chosen by hand"})
        line = documents.fiscal_line_ids
        line.product_id = product
        line.import_uom_factor = 12

        line._apply_import_depara(product=product, uom=self.uom_unit)

        self.assertEqual(line.quantity, 120)
        self.assertEqual(line.fiscal_amount_untaxed, 350)
        self.assertEqual(documents.fiscal_amount_untaxed, 350)
        line.price_unit = 3
        self.assertEqual(line.fiscal_amount_untaxed, 360)

    def test_product_found_by_internal_code_is_only_a_suggestion(self):
        product = self.env["product.product"].create(
            {"name": "Same code", "default_code": "ZZ-NEW-1"}
        )
        infos = self.env["product.supplierinfo"].search_count([])

        documents = self._imported(self._depara_note(KEY_2))

        line = documents.fiscal_line_ids
        self.assertEqual(line.product_id, product)
        self.assertEqual(line.import_state, "matched")
        self.assertEqual(self.env["product.supplierinfo"].search_count([]), infos)
        documents.action_import_confirm_suggestions()
        self.assertEqual(line.import_state, "resolved")
        self.assertEqual(documents.import_state, "resolved")

    def test_product_without_any_match_stays_pending(self):
        line = self._imported(
            self._depara_note(KEY_2, code=b"NO-MATCH-1")
        ).fiscal_line_ids

        self.assertEqual(line.import_state, "pending")

    def test_resolving_by_hand_teaches_the_next_note_of_the_supplier(self):
        first = self._imported(self._depara_note(KEY_2, code=b"NO-MATCH-2"))
        product = self.env["product.product"].create({"name": "Chosen by hand"})
        line = first.fiscal_line_ids
        line.product_id = product
        line._apply_import_depara(product=product, uom=self.uom_unit)
        domain = [("product_code", "=", "NO-MATCH-2"), ("product_id", "=", product.id)]
        self.assertEqual(self.env["product.supplierinfo"].search_count(domain), 1)

        second = self._imported(self._depara_note(KEY_3, code=b"NO-MATCH-2"))

        self.assertEqual(second.fiscal_line_ids.product_id, product)
        self.assertEqual(second.fiscal_line_ids.import_state, "resolved")
        self.assertEqual(self.env["product.supplierinfo"].search_count(domain), 1)

    def test_learned_factor_only_holds_for_the_same_declared_unit(self):
        kilo = self.env["uom.uom"]._match_by_fiscal_code("KG")
        product = self._supplier_product(
            uom=kilo, partner_uom_id=kilo.id, partner_uom_factor=2
        )

        same = self._imported(self._depara_note(KEY_2, unit=b"KG"), name="kg.xml")
        other = self._imported(self._depara_note(KEY_3, unit=b"UN"), name="un.xml")

        self.assertEqual(same.fiscal_line_ids.product_id, product)
        self.assertEqual(same.fiscal_line_ids.import_state, "resolved")
        self.assertEqual(same.fiscal_line_ids.quantity, 2)
        self.assertEqual(other.fiscal_line_ids.import_state, "matched")
        self.assertEqual(other.fiscal_line_ids.quantity, 2)

    def test_product_mapped_for_another_supplier_is_not_resolved(self):
        other = self.env["res.partner"].create({"name": "Another supplier"})
        product = self._supplier_product()
        product.seller_ids.write({"partner_id": other.id})

        line = self._imported(self._depara_note(KEY_2)).fiscal_line_ids

        self.assertEqual(line.import_state, "pending")

    def test_resolving_by_hand_records_the_declared_unit_and_factor(self):
        kilo = self.env["uom.uom"]._match_by_fiscal_code("KG")
        first = self._imported(self._depara_note(KEY_2, unit=b"KG", code=b"NO-MATCH-3"))
        product = self.env["product.product"].create({"name": "Chosen by hand"})
        line = first.fiscal_line_ids
        line.product_id = product
        line.import_uom_factor = 2

        line._apply_import_depara(product=product, uom=self.uom_unit)

        info = self.env["product.supplierinfo"].search(
            [("product_code", "=", "NO-MATCH-3")]
        )
        self.assertEqual((info.partner_uom_id, info.partner_uom_factor), (kilo, 2))

    # The common fiscal user: the group that imports, reviews and confirms.

    def test_common_fiscal_user_imports_the_file_as_the_author(self):
        user = self._fiscal_user("fiscal_nfe_import")
        service = self.Document.with_user(user).with_context(
            allowed_company_ids=[self.company.id]
        )

        documents = self._imported(self._xml(KEY_1), model=service)

        self.assertEqual(documents.create_uid, user)
        self.assertEqual(documents.original_xml_file_id.create_uid, user)
        self.assertTrue(documents.nfe40_detPag)

    def test_common_fiscal_user_resolves_the_line_and_the_de_para_is_learned(self):
        user = self._fiscal_user("fiscal_nfe_depara")
        service = self.Document.with_user(user).with_context(
            allowed_company_ids=[self.company.id]
        )
        documents = self._imported(self._xml(KEY_1), model=service)
        product = self.env["product.product"].create({"name": "Chosen"})
        line = documents.fiscal_line_ids

        line.product_id = product
        line._apply_import_depara(product=product, uom=self.uom_unit)

        self.assertEqual(line.import_state, "resolved")
        self.assertEqual(line.write_uid, user)
        self.assertTrue(line.import_supplierinfo_id)

    def test_common_fiscal_user_of_another_company_cannot_import_the_note(self):
        user = self._fiscal_user("fiscal_nfe_other", self.other_company)
        service = self.Document.with_user(user).with_context(
            allowed_company_ids=[self.other_company.id]
        )

        documents, errors, _warnings = self._import(self._xml(KEY_1), model=service)

        self.assertFalse(documents)
        self.assertIn("no access to the company", errors[0][1])

    # What the NF-e declares to be paid: the duplicates (dup) and the payments (detPag).

    def _collection_xml(self, key, installments, means="15", term="1"):
        """The note with a collection (cobr) of the given ``(date, amount)`` and
        the payment declared as ``means`` and ``term``."""
        cobr = (
            "<cobr><fat><nFat>1</nFat><vOrig>140.00</vOrig><vDesc>0.00</vDesc>"
            "<vLiq>140.00</vLiq></fat>"
        )
        for number, (due, amount) in enumerate(installments, 1):
            cobr += (
                f"<dup><nDup>{number:03d}</nDup><dVenc>{due}</dVenc>"
                f"<vDup>{amount:.2f}</vDup></dup>"
            )
        cobr += "</cobr>"
        return self._xml(
            key,
            replace=[
                (b"<pag>", cobr.encode() + b"<pag>"),
                (b"<indPag>0</indPag>", f"<indPag>{term}</indPag>".encode()),
                (b"<tPag>01</tPag>", f"<tPag>{means}</tPag>".encode()),
            ],
        )

    def test_the_duplicates_and_the_payment_declared_are_read(self):
        xml = self._collection_xml(KEY_1, [("2026-12-10", 70.0), ("2027-01-10", 70.0)])

        document = self._imported(xml)

        self.assertEqual(
            document._edi_get_installments(),
            [
                EdiInstallment("001", date(2026, 12, 10), 70.0),
                EdiInstallment("002", date(2027, 1, 10), 70.0),
            ],
        )
        self.assertEqual(
            document._edi_get_payments(), [EdiPayment("15", 140.0, "installments")]
        )

    def test_a_note_without_collection_declares_only_the_payment(self):
        document = self._imported(self._xml(KEY_1))

        self.assertEqual(document._edi_get_installments(), [])
        self.assertEqual(
            document._edi_get_payments(), [EdiPayment("01", 140.0, "cash")]
        )
        summary = str(document.edi_payment_summary)
        self.assertIn("Payments", summary)
        self.assertNotIn("Installments", summary)

    def test_the_page_of_installments_shows_the_declared_ones(self):
        xml = self._collection_xml(KEY_1, [("2026-12-10", 70.0), ("2027-01-10", 70.0)])

        document = self._imported(xml)

        summary = str(document.edi_payment_summary)
        for text in ("001", "002", "70.00", "12/10/2026", "01/10/2027"):
            self.assertIn(text, summary)
        self.assertNotIn("alert-warning", summary)
        self.assertNotIn("installments add up", document.import_warning or "")

    def test_installments_that_do_not_add_up_to_the_net_amount_are_warned(self):
        xml = self._collection_xml(KEY_1, [("2026-12-10", 60.0), ("2027-01-10", 70.0)])

        document = self._imported(xml)

        self.assertIn("130.00", str(document.edi_payment_summary))
        self.assertIn("alert-warning", str(document.edi_payment_summary))
        self.assertIn("installments add up", document.import_warning)

    def test_common_fiscal_user_imports_the_note_with_collection_and_volumes(self):
        user = self._fiscal_user("fiscal_nfe_collection")
        service = self.Document.with_user(user).with_context(
            allowed_company_ids=[self.company.id]
        )
        xml = self._collection_xml(
            KEY_1, [("2026-12-10", 70.0), ("2027-01-10", 70.0)]
        ).replace(
            b"<modFrete>9</modFrete>",
            b"<modFrete>9</modFrete><vol><qVol>2</qVol></vol>",
        )

        document = self._imported(xml, model=service)

        self.assertEqual(len(document._edi_get_installments()), 2)
        self.assertEqual(document.nfe40_vol.nfe40_qVol, "2")

    # The nature of the operation, the partner that is missing and the own note.

    def test_the_nature_declared_in_the_file_chooses_among_operations_of_the_cfop(
        self,
    ):
        operation = self.env["l10n_br_fiscal.operation"].create(
            {
                "code": "TST-VENDA",
                "name": "Venda",
                "fiscal_operation_type": "in",
                "fiscal_type": "purchase",
            }
        )
        self.env["l10n_br_fiscal.operation.line"].create(
            {
                "fiscal_operation_id": operation.id,
                "name": "Venda",
                "cfop_internal_id": self.env.ref("l10n_br_fiscal.cfop_1102").id,
            }
        )
        operation.action_approve()

        document = self._imported(self._xml(KEY_1))
        other = self._imported(
            self._xml(KEY_2, replace=[(b"<natOp>Venda", b"<natOp>Another nature")])
        )

        self.assertEqual(document.partner_operation_name, "Venda")
        self.assertEqual(document.fiscal_operation_id, operation)
        self.assertEqual(other.partner_operation_name, "Another nature")
        self.assertNotEqual(other.fiscal_operation_id, operation)
