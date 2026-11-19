# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import os
import re

import nfelib

from odoo.addons.l10n_br_fiscal_edi.tests.common import EdiImportCase

NFSE_SAMPLE = os.path.join(
    os.path.dirname(nfelib.__file__), "nfse", "samples", "v1_0", "nfse-ibscbs.xml"
)
SAMPLE_KEY = "42024042200000000000000000000000000126031234567892"
SAMPLE_CNPJ = "00000000000000"
# CNPJ of the partner and of the company of the demo data
PROVIDER = "59594315000157"
LUCRO_PRESUMIDO = "81583054000129"
LUCRO_REAL = "46312887000154"
UNKNOWN_PROVIDER = "12345678000195"
WITHHOLDINGS = (
    "<tribFed><piscofins><CST>01</CST><vBCPisCofins>1000.00</vBCPisCofins>"
    "<pAliqPis>0.65</pAliqPis><pAliqCofins>3.00</pAliqCofins><vPis>6.50</vPis>"
    "<vCofins>30.00</vCofins><tpRetPisCofins>3</tpRetPisCofins></piscofins>"
    "<vRetIRRF>15.00</vRetIRRF><vRetCSLL>46.50</vRetCSLL></tribFed>"
)


def nfse_xml(taker=LUCRO_PRESUMIDO, provider=PROVIDER, withholdings=False):
    """The national NFS-e that nfelib ships as a sample, with the parties moved to
    the partners and the companies of the demo data.

    :param withholdings: PIS and COFINS withheld, and IRRF and CSLL as well
    """
    with open(NFSE_SAMPLE, encoding="utf-8") as handle:
        xml = handle.read()
    xml = re.sub(r"(<toma>\s*<CNPJ>)\d+", rf"\g<1>{taker}", xml)
    xml = xml.replace(f"<CNPJ>{SAMPLE_CNPJ}</CNPJ>", f"<CNPJ>{provider}</CNPJ>")
    if withholdings:
        xml = xml.replace("</tribMun>", f"</tribMun>{WITHHOLDINGS}", 1)
    return xml.encode()


class TestNfseDocumentImport(EdiImportCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.presumed = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.provider = cls.env["res.partner"].search(
            [("cnpj_cpf_stripped", "=", PROVIDER)], limit=1
        )

    def _import(self, content, model=None, operation=False):
        """Import the file; with ``operation``, a person has chosen the operation
        line of the service, as the review asks."""
        documents, errors, warnings = (
            self.Document if model is None else model
        )._edi_import_files([("nfse.xml", content)])
        if operation and documents:
            documents.fiscal_line_ids.fiscal_operation_line_id = self.env.ref(
                "l10n_br_fiscal.fo_compras_compras"
            )
        return documents, errors, warnings

    def test_a_nfse_is_read_and_becomes_a_document_of_the_taker(self):
        documents, errors, _warnings = self._import(nfse_xml())
        self.assertFalse(errors)
        self.assertEqual(documents.document_key, SAMPLE_KEY)
        self.assertEqual(documents.document_type_id.code, "SE")
        self.assertEqual(documents.company_id, self.presumed)
        self.assertTrue(documents.imported_document)
        self.assertEqual(documents.issuer, "partner")
        self.assertEqual(documents.fiscal_operation_id.fiscal_operation_type, "in")
        self.assertEqual(documents.fiscal_operation_type, "in")
        self.assertEqual(documents.partner_id, self.provider)
        self.assertEqual(documents.document_serie, "00007")
        self.assertTrue(documents.original_xml_file_id)
        line = documents.fiscal_line_ids
        self.assertEqual(line.name, "Desenvolvimento de sistema sob encomenda")
        self.assertAlmostEqual(line.price_unit, 1000.0)
        self.assertAlmostEqual(line.issqn_value, 20.0)
        self.assertEqual(line.import_state, "pending")

    def test_the_incidence_city_of_the_file_survives_a_recompute(self):
        documents, _errors, _warnings = self._import(nfse_xml())
        line = documents.fiscal_line_ids
        city = line.issqn_fg_city_id
        self.assertEqual(city.ibge_code, "4202404")
        self.assertNotEqual(city, self.presumed.partner_id.city_id)
        line._compute_issqn_fg_city_id()
        self.assertEqual(line.issqn_fg_city_id, city)

    def test_the_company_is_the_taker_of_the_service(self):
        parsed = self.Document._edi_import_read("a.xml", nfse_xml(taker=LUCRO_REAL))
        self.assertEqual(parsed.company_vats, (("taker", LUCRO_REAL),))
        self.assertEqual((parsed.reader, parsed.document_type_code), ("nfse", "SE"))
        self.assertEqual(parsed.issuer_vat, PROVIDER)
        documents, errors, _warnings = self._import(nfse_xml(taker=LUCRO_REAL))
        self.assertFalse(errors)
        self.assertEqual(documents.company_id, self.other_company)

    def test_a_nfse_for_no_company_is_refused(self):
        documents, errors, _warnings = self._import(nfse_xml(taker=UNKNOWN_PROVIDER))
        self.assertFalse(documents)
        self.assertIn("No company of this database", errors[0][1])

    def test_a_nfse_without_a_valid_access_key_is_refused(self):
        content = nfse_xml().replace(b'Id="NFS4202404', b'Id="NFS420')
        documents, errors, _warnings = self._import(content)
        self.assertFalse(documents)
        self.assertIn("50-digit access key", errors[0][1])

    def test_a_file_that_is_not_a_nfse_is_not_read_by_the_nfse_reader(self):
        nfe = '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe/></nfeProc>'
        cte = '<cteProc xmlns="http://www.portalfiscal.inf.br/cte"><CTe/></cteProc>'
        for content in (nfe, cte, "<root/>", "not xml at all"):
            self.assertIsNone(self.Document._edi_import_read("a.xml", content.encode()))
        documents, errors, _warnings = self._import(nfe.encode())
        self.assertFalse(documents)
        self.assertIn("not a fiscal document", errors[0][1])

    def test_the_same_nfse_twice_opens_the_same_document(self):
        documents, _errors, _warnings = self._import(nfse_xml())
        again, errors, warnings = self._import(nfse_xml())
        self.assertEqual(again, documents)
        self.assertFalse(errors)
        self.assertEqual(len(warnings), 1)

    def test_the_provider_that_is_unknown_is_created_and_recorded(self):
        self.assertFalse(
            self.env["res.partner"].search(
                [("cnpj_cpf_stripped", "=", UNKNOWN_PROVIDER)], limit=1
            )
        )
        documents, errors, _warnings = self._import(nfse_xml(provider=UNKNOWN_PROVIDER))
        self.assertFalse(errors)
        provider = documents.partner_id
        self.assertEqual(provider.cnpj_cpf_stripped, UNKNOWN_PROVIDER)
        self.assertEqual(provider.legal_name, "EMPRESA PRESTADORA DE TESTE LTDA")
        self.assertTrue(provider.is_company)
        self.assertIn(provider.display_name, documents.message_ids[0].body)

    def test_the_service_product_of_the_company_goes_to_the_line(self):
        product = self.env["product.product"].create(
            {"name": "Imported NFS-e service", "type": "service"}
        )
        self.presumed.nfse_import_product_id = product
        documents, _errors, _warnings = self._import(nfse_xml())
        self.assertEqual(documents.fiscal_line_ids.product_id, product)

    def test_a_nfse_without_withholdings_has_no_page(self):
        documents, _errors, _warnings = self._import(nfse_xml(), operation=True)
        self.assertEqual(documents.amount_tax_withholding, 0.0)
        self.assertFalse(documents.edi_payment_summary)

    def test_a_nfse_with_withholdings_shows_them_and_the_net_amount(self):
        documents, errors, _warnings = self._import(
            nfse_xml(withholdings=True), operation=True
        )
        self.assertFalse(errors)
        line = documents.fiscal_line_ids
        self.assertAlmostEqual(line.pis_wh_value, 6.5)
        self.assertAlmostEqual(line.cofins_wh_value, 30.0)
        self.assertAlmostEqual(line.irpj_wh_value, 15.0)
        self.assertAlmostEqual(line.csll_wh_value, 10.0)
        self.assertAlmostEqual(documents.amount_tax_withholding, 61.5)
        self.assertAlmostEqual(documents.amount_financial_total, 938.5)
        self.assertEqual(documents._edi_get_installments(), [])
        summary = str(documents.edi_payment_summary)
        for text in ("Withholdings", "61.50", "Net amount payable", "938.50"):
            self.assertIn(text, summary)

    def test_a_common_fiscal_user_imports_a_nfse(self):
        user = self._fiscal_user("fiscal_user_nfse", self.presumed)
        model = self.Document.with_user(user).with_context(
            allowed_company_ids=self.presumed.ids
        )
        documents, errors, _warnings = self._import(
            nfse_xml(withholdings=True), model, operation=True
        )
        self.assertFalse(errors)
        self.assertEqual(documents.create_uid, user)
        self.assertAlmostEqual(documents.amount_tax_withholding, 61.5)
        self.assertIn("61.50", str(documents.edi_payment_summary))
