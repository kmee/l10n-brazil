# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tools import file_open

from odoo.addons.l10n_br_fiscal_edi.tests.common import EdiImportCase

CTE_KEY = "35240759594315000157570010000057311040445890"
CTE_FILE = f"l10n_br_cte/tests/cte/v4_00/leiauteCTe/CTe{CTE_KEY}.xml"
# CNPJ of the recipient in the file, and of the companies of the demo data
FILE_RECIPIENT = "46081676000158"
LUCRO_REAL = "46312887000154"
LUCRO_PRESUMIDO = "81583054000129"
NAMESPACE = "http://www.portalfiscal.inf.br/cte"
PROTOCOL = (
    '<protCTe versao="4.00"><infProt><tpAmb>2</tpAmb><verAplic>SP_CTE_PL_4.00'
    "</verAplic><chCTe>%(key)s</chCTe><dhRecbto>2024-07-10T10:00:00-03:00"
    "</dhRecbto><nProt>135240000000002</nProt><digVal>YWJj</digVal>"
    "<cStat>%(status)s</cStat><xMotivo>x</xMotivo></infProt></protCTe>"
)


OTHER_DOCUMENT = (
    "<infOutros><tpDoc>99</tpDoc><descOutros>Contract</descOutros><nDoc>7</nDoc>"
    "<dEmi>2024-07-01</dEmi><vDocFisc>50.00</vDocFisc></infOutros>"
)


def cte_xml(
    taker=None,
    recipient=LUCRO_REAL,
    status=None,
    related=False,
):
    """The demo CT-e, with the recipient moved to a company of the demo data.

    :param taker: CNPJ of a taker that is not the recipient (``toma4``)
    :param status: cStat of the protocol; the CT-e then comes as a ``cteProc``
    """
    with file_open(CTE_FILE, "rb") as handle:
        xml = handle.read().decode()
    xml = xml.replace(FILE_RECIPIENT, recipient)
    if related:
        xml = xml.replace("</infNFe>", f"</infNFe>{OTHER_DOCUMENT}", 1)
    if taker:
        xml = xml.replace(
            "<toma3>\n        <toma>3</toma>\n      </toma3>",
            f"<toma4><toma>4</toma><CNPJ>{taker}</CNPJ><xNome>Taker</xNome></toma4>",
        )
    if status:
        body = xml.split("?>", 1)[1].strip()
        xml = (
            f'<cteProc xmlns="{NAMESPACE}" versao="4.00">{body}'
            + PROTOCOL % {"key": CTE_KEY, "status": status}
            + "</cteProc>"
        )
    return xml.encode()


class TestCteDocumentImport(EdiImportCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.presumed = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        # the demo CT-e of the Simples Nacional company has this key
        cls.Document.search([("document_key", "=", CTE_KEY)]).unlink()

    def _import(self, content, model=None, operation=False):
        """Import the file; with ``operation``, a person has chosen the operation of
        the document and of its line, as the review asks."""
        documents, errors, warnings = (
            self.Document if model is None else model
        )._edi_import_files([(f"{CTE_KEY}.xml", content)])
        if operation and documents:
            documents.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
            documents.fiscal_line_ids.fiscal_operation_line_id = self.env.ref(
                "l10n_br_fiscal.fo_compras_compras"
            )
        return documents, errors, warnings

    def test_a_cte_is_read_and_becomes_a_document_of_the_recipient(self):
        documents, errors, _warnings = self._import(cte_xml(status="100"))
        self.assertFalse(errors)
        self.assertEqual(documents.document_key, CTE_KEY)
        self.assertEqual(documents.document_type_id.code, "57")
        self.assertEqual(documents.company_id, self.other_company)
        self.assertTrue(documents.imported_document)
        self.assertEqual(documents.issuer, "partner")
        self.assertEqual(documents.partner_id.cnpj_cpf_stripped, "59594315000157")
        self.assertTrue(documents.original_xml_file_id)
        line = documents.fiscal_line_ids
        self.assertEqual(line.partner_cfop_id.code, "5352")
        self.assertEqual(line.import_state, "pending")

    def test_the_status_comes_from_the_protocol_of_the_cte(self):
        for status, expected in (
            ("100", "authorized"),
            ("101", "cancelled"),
            ("110", "denied"),
            ("999", "unknown"),
        ):
            parsed = self.Document._edi_import_read("a.xml", cte_xml(status=status))
            self.assertEqual((parsed.status, parsed.status_code), (expected, status))
        parsed = self.Document._edi_import_read("a.xml", cte_xml())
        self.assertEqual((parsed.status, parsed.status_code), ("unknown", ""))

    def test_a_cancelled_cte_is_refused(self):
        documents, errors, _warnings = self._import(cte_xml(status="101"))
        self.assertFalse(documents)
        self.assertIn("cancelled", errors[0][1])

    def test_the_company_is_the_taker_before_the_recipient(self):
        parsed = self.Document._edi_import_read("a.xml", cte_xml(taker=LUCRO_PRESUMIDO))
        self.assertEqual(
            parsed.company_vats,
            (
                ("taker", LUCRO_PRESUMIDO),
                ("recipient", LUCRO_REAL),
                ("recipient", "12046835000161"),
            ),
        )
        documents, errors, _warnings = self._import(cte_xml(taker=LUCRO_PRESUMIDO))
        self.assertFalse(errors)
        self.assertEqual(documents.company_id, self.presumed)

    def test_the_company_is_the_recipient_when_the_taker_is_not_one(self):
        documents, errors, _warnings = self._import(cte_xml(taker="12345678000195"))
        self.assertFalse(errors)
        self.assertEqual(documents.company_id, self.other_company)

    def test_a_cte_for_no_company_is_refused(self):
        documents, errors, _warnings = self._import(cte_xml(recipient="12345678000195"))
        self.assertFalse(documents)
        self.assertIn("No company of this database", errors[0][1])

    def test_a_cte_os_and_a_gtve_are_refused_with_the_reason(self):
        for root, kind in (
            ("cteOSProc", "CT-e OS"),
            ("CTeOS", "CT-e OS"),
            ("GTVe", "GTV-e"),
            ("GTVeProc", "GTV-e"),
            ("CTeSimp", "CT-e Simp"),
        ):
            content = f'<{root} xmlns="{NAMESPACE}" versao="4.00"/>'.encode()
            documents, errors, _warnings = self._import(content)
            self.assertFalse(documents, root)
            self.assertIn("Only the CT-e (model 57)", errors[0][1], root)
            self.assertIn(kind, errors[0][1], root)

    def test_a_broken_cte_is_refused_as_invalid(self):
        for content in (
            f'<cteProc xmlns="{NAMESPACE}"><CTe/></cteProc>',
            f'<CTe xmlns="{NAMESPACE}"><infCte Id="CTe123"/></CTe>',
            f'<cteProc xmlns="{NAMESPACE}"><unknown/></cteProc>',
        ):
            documents, errors, _warnings = self._import(content.encode())
            self.assertFalse(documents)
            self.assertIn("not a valid CT-e", errors[0][1])

    def test_a_file_that_is_not_a_cte_is_not_read_by_the_cte_reader(self):
        nfse = (
            '<NFSe xmlns="http://www.sped.fazenda.gov.br/nfse"><infNFSe Id="NFS1"/>'
            "</NFSe>"
        )
        nfe = '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe/></nfeProc>'
        other_namespace = '<cteProc xmlns="http://example.com/other"/>'
        for content in (nfse, nfe, other_namespace, "not xml at all"):
            self.assertIsNone(self.Document._edi_import_read("a.xml", content.encode()))
        documents, errors, _warnings = self._import(nfe.encode())
        self.assertFalse(documents)
        self.assertIn("not a fiscal document", errors[0][1])

    def test_a_common_fiscal_user_imports_a_cte_with_every_related_document(self):
        user = self._fiscal_user("fiscal_user_cte_related", self.other_company)
        model = self.Document.with_user(user).with_context(
            allowed_company_ids=self.other_company.ids
        )
        documents, errors, _warnings = self._import(
            cte_xml(related=True), model, operation=True
        )
        self.assertFalse(errors)
        self.assertEqual(len(documents), 1)

    def test_a_common_fiscal_user_imports_a_cte(self):
        user = self._fiscal_user("fiscal_user_cte", self.other_company)
        model = self.Document.with_user(user).with_context(
            allowed_company_ids=self.other_company.ids
        )
        documents, errors, _warnings = self._import(cte_xml(), model)
        self.assertFalse(errors)
        self.assertEqual(documents.create_uid, user)
