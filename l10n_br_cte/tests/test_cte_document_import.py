# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re
from datetime import date
from unittest.mock import patch

from odoo.tools import file_open

from odoo.addons.l10n_br_fiscal_edi.tests.common import EdiImportCase
from odoo.addons.l10n_br_fiscal_edi.tools import EdiInstallment

CTE_KEY = "35240759594315000157570010000057311040445890"
CTE_FILE = f"l10n_br_cte/tests/cte/v4_00/leiauteCTe/CTe{CTE_KEY}.xml"
# CNPJ of the recipient in the file, and of the companies of the demo data
FILE_RECIPIENT = "46081676000158"
LUCRO_REAL = "46312887000154"
LUCRO_PRESUMIDO = "81583054000129"
COLLECTION = (
    "<cobr><fat><nFat>1</nFat><vOrig>100.00</vOrig><vLiq>100.00</vLiq></fat>"
    "<dup><nDup>002</nDup><dVenc>2027-01-10</dVenc><vDup>60.00</vDup></dup>"
    "<dup><nDup>001</nDup><dVenc>2026-12-10</dVenc><vDup>40.00</vDup></dup>"
    "</cobr>"
)
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
    collection=None,
    taker=None,
    recipient=LUCRO_REAL,
    status=None,
    related=False,
    emitter=None,
):
    """The demo CT-e, with the recipient moved to a company of the demo data.

    :param collection: the ``cobr`` group to add to the CT-e
    :param taker: CNPJ of a taker that is not the recipient (``toma4``)
    :param emitter: CNPJ of the issuer, when it is not the one of the file
    :param status: cStat of the protocol; the CT-e then comes as a ``cteProc``
    """
    with file_open(CTE_FILE, "rb") as handle:
        xml = handle.read().decode()
    xml = xml.replace(FILE_RECIPIENT, recipient)
    if emitter:
        xml = re.sub(r"(<emit>\s*<CNPJ>)\d+", rf"\g<1>{emitter}", xml)
    if related:
        xml = xml.replace("</infNFe>", f"</infNFe>{OTHER_DOCUMENT}", 1)
    if collection:
        xml = xml.replace("</infCTeNorm>", f"{collection}</infCTeNorm>")
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
        # and the demo CT-e of the company that issues the number of the file
        cls.Document.search(
            [
                ("company_id", "=", cls.presumed.id),
                ("document_type_id.code", "=", "57"),
                ("document_number", "=", "573"),
            ]
        ).unlink()

    def _import(self, content, model=None, operation=False, issued=False):
        """Import the file; with ``operation``, a person has chosen the operation of
        the document and of its line, as the review asks."""
        documents, errors, warnings = (
            self.Document if model is None else model
        )._edi_import_files([(f"{CTE_KEY}.xml", content)])
        if operation and documents:
            prefix = "fo_venda" if issued else "fo_compras"
            documents.fiscal_operation_id = self.env.ref(f"l10n_br_fiscal.{prefix}")
            documents.fiscal_line_ids.fiscal_operation_line_id = self.env.ref(
                f"l10n_br_fiscal.{prefix}_{'venda' if issued else 'compras'}"
            )
        return documents, errors, warnings

    def _freight(self, **values):
        return self.env["product.product"].create(
            dict({"name": "Freight service", "type": "service"}, **values)
        )

    def test_the_nature_of_the_operation_of_the_file_is_kept(self):
        documents, _errors, _warnings = self._import(cte_xml())
        self.assertEqual(documents.partner_operation_name, "Venda")
        content = cte_xml(recipient="12345678000195", emitter=LUCRO_PRESUMIDO)
        issued, _errors, _warnings = self._import(content)
        self.assertEqual(issued.partner_operation_name, "Venda")

    def test_the_default_freight_product_is_a_suggestion_on_the_line(self):
        product = self._freight(uom_id=self.env.ref("uom.product_uom_dozen").id)
        self.other_company.cte_import_product_id = product
        documents, errors, _warnings = self._import(cte_xml())
        self.assertFalse(errors)
        line = documents.fiscal_line_ids
        self.assertEqual(line.product_id, product)
        self.assertEqual(line.uom_id, product.uom_id)
        self.assertEqual(line.import_state, "matched")

    def test_without_the_default_product_the_line_waits_for_the_choice(self):
        documents, _errors, _warnings = self._import(cte_xml())
        line = documents.fiscal_line_ids
        self.assertFalse(line.product_id)
        self.assertEqual(line.import_state, "pending")

    def test_confirming_the_suggestions_resolves_the_freight_line(self):
        self.other_company.cte_import_product_id = self._freight()
        documents, _errors, _warnings = self._import(cte_xml())
        self.assertEqual(documents.fiscal_line_ids.import_state, "matched")
        documents.action_import_confirm_suggestions()
        self.assertEqual(documents.fiscal_line_ids.import_state, "resolved")

    def test_a_product_of_another_company_is_not_suggested(self):
        self.other_company.cte_import_product_id = self._freight(
            company_id=self.presumed.id
        )
        user = self._fiscal_user("fiscal_user_cte_product", self.other_company)
        model = self.Document.with_user(user).with_context(
            allowed_company_ids=self.other_company.ids
        )
        documents, errors, _warnings = self._import(cte_xml(), model)
        self.assertFalse(errors)
        line = documents.fiscal_line_ids
        self.assertFalse(line.product_id)
        self.assertEqual(line.import_state, "pending")

    def test_a_cte_issued_by_the_company_does_not_get_the_freight_product(self):
        self.presumed.cte_import_product_id = self._freight()
        content = cte_xml(recipient="12345678000195", emitter=LUCRO_PRESUMIDO)
        documents, errors, _warnings = self._import(content)
        self.assertFalse(errors)
        self.assertFalse(documents.fiscal_line_ids.product_id)

    def test_a_user_who_cannot_create_contacts_is_told_which_partner_is_missing(self):
        user = self._fiscal_user("fiscal_user_cte_partner", self.other_company)
        model = self.Document.with_user(user).with_context(
            allowed_company_ids=self.other_company.ids
        )
        documents, errors, _warnings = self._import(
            cte_xml(emitter="12345678000195"), model
        )
        self.assertFalse(documents)
        message = errors[0][1]
        self.assertIn("Empresa Simples Nacional", message)
        self.assertIn("12.345.678/0001-95", message)
        self.assertIn("not allowed to create contacts", message)

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

    def test_a_cte_whose_protocol_does_not_authorize_it_is_refused(self):
        documents, errors, _warnings = self._import(cte_xml(status="999"))
        self.assertFalse(documents)
        self.assertIn("not authorized (status 999)", errors[0][1])

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
                ("issuer", "59594315000157"),
            ),
        )
        documents, errors, _warnings = self._import(cte_xml(taker=LUCRO_PRESUMIDO))
        self.assertFalse(errors)
        self.assertEqual(documents.company_id, self.presumed)

    def test_the_company_is_the_recipient_when_the_taker_is_not_one(self):
        documents, errors, _warnings = self._import(cte_xml(taker="12345678000195"))
        self.assertFalse(errors)
        self.assertEqual(documents.company_id, self.other_company)

    def _sequences(self):
        return self.env["ir.sequence"].search([]).read(["id", "number_next_actual"])

    def test_a_cte_issued_by_the_company_becomes_an_outgoing_document(self):
        sequences = self._sequences()
        content = cte_xml(
            COLLECTION, recipient="12345678000195", emitter=LUCRO_PRESUMIDO
        )
        documents, errors, _warnings = self._import(content)
        self.assertFalse(errors)
        self.assertEqual(documents.fiscal_operation_type, "out")
        self.assertEqual(documents.company_id, self.presumed)
        self.assertEqual(documents.issuer, "company")
        self.assertEqual(documents.state_edoc, "em_digitacao")
        self.assertTrue(documents.imported_document)
        self.assertEqual(documents.partner_id.cnpj_cpf_stripped, "12345678000195")
        self.assertEqual(documents.document_key, CTE_KEY)
        self.assertEqual(
            (documents.document_number, documents.document_serie), ("573", "1")
        )
        self.assertAlmostEqual(documents.fiscal_line_ids.price_unit, 100.0)
        self.assertEqual(
            [i.amount for i in documents._edi_get_installments()], [40.0, 60.0]
        )
        self.assertEqual(self._sequences(), sequences)

    def test_confirming_a_cte_issued_by_the_company_neither_sends_nor_learns(self):
        self.presumed.cte_import_product_id = False
        content = cte_xml(recipient="12345678000195", emitter=LUCRO_PRESUMIDO)
        documents, _errors, _warnings = self._import(
            content, operation=True, issued=True
        )
        line = documents.fiscal_line_ids
        line.product_id = self._freight()
        line.action_resolve_line()
        sequences = self._sequences()
        with patch.object(type(documents), "_document_export") as export:
            documents.action_document_confirm()
        export.assert_called_once()
        self.assertEqual(documents.state_edoc, "autorizada")
        self.assertEqual(documents.document_number, "573")
        self.assertEqual(self._sequences(), sequences)
        self.assertFalse(documents.send_file_id)
        self.assertFalse(
            self.env["product.supplierinfo"].search(
                [("partner_id", "=", documents.partner_id.id)]
            )
        )

    def test_a_cte_where_the_company_is_issuer_and_taker_enters_as_the_taker(self):
        content = cte_xml(taker=LUCRO_PRESUMIDO, emitter=LUCRO_PRESUMIDO)
        documents, errors, _warnings = self._import(content)
        self.assertFalse(errors)
        self.assertEqual(documents.company_id, self.presumed)
        self.assertEqual(documents.issuer, "partner")
        self.assertEqual(documents.fiscal_operation_type, "in")

    def test_a_cte_for_no_company_is_refused(self):
        content = cte_xml(recipient="12345678000195", emitter="11444777000161")
        documents, errors, _warnings = self._import(content)
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

    def test_a_cte_with_a_collection_declares_its_installments_in_order(self):
        documents, errors, _warnings = self._import(cte_xml(COLLECTION))
        self.assertFalse(errors)
        self.assertEqual(len(documents.cte40_cobr.cte40_dup), 2)
        self.assertEqual(
            documents._edi_get_installments(),
            [
                EdiInstallment("001", date(2026, 12, 10), 40.0),
                EdiInstallment("002", date(2027, 1, 10), 60.0),
            ],
        )

    def test_the_page_of_a_cte_with_a_collection_shows_the_installments(self):
        documents, _errors, _warnings = self._import(
            cte_xml(COLLECTION), operation=True
        )
        summary = str(documents.edi_payment_summary)
        for text in ("001", "002", "40.00", "60.00", "12/10/2026", "01/10/2027"):
            self.assertIn(text, summary)
        self.assertFalse(documents._edi_installment_difference())
        self.assertNotIn("add up", summary)

    def test_installments_that_do_not_add_up_to_the_document_raise_a_warning(self):
        collection = COLLECTION.replace("60.00", "90.00")
        documents, _errors, _warnings = self._import(
            cte_xml(collection), operation=True
        )
        self.assertEqual(documents._edi_installment_difference(), -30.0)
        self.assertIn("add up", str(documents.edi_payment_summary))
        self.assertIn("add up", documents.import_warning)

    def test_a_cte_without_a_collection_declares_no_installment(self):
        documents, errors, _warnings = self._import(cte_xml())
        self.assertFalse(errors)
        self.assertEqual(documents._edi_get_installments(), [])
        self.assertFalse(documents.edi_payment_summary)

    def test_an_installment_without_date_or_amount_is_not_declared(self):
        collection = (
            "<cobr><dup><nDup>001</nDup><vDup>50.00</vDup></dup>"
            "<dup><nDup>002</nDup><dVenc>2026-12-10</dVenc></dup>"
            "<dup><nDup>003</nDup><dVenc>2026-12-20</dVenc><vDup>20.00</vDup></dup>"
            "</cobr>"
        )
        documents, _errors, _warnings = self._import(cte_xml(collection))
        self.assertEqual(
            documents._edi_get_installments(),
            [EdiInstallment("003", date(2026, 12, 20), 20.0)],
        )

    def test_another_type_of_document_declares_no_cte_installment(self):
        documents, _errors, _warnings = self._import(cte_xml(COLLECTION))
        documents.document_type_id = self.env.ref("l10n_br_fiscal.document_55")
        self.assertEqual(documents._edi_get_installments(), [])

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
        documents, errors, _warnings = self._import(
            cte_xml(COLLECTION), model, operation=True
        )
        self.assertFalse(errors)
        self.assertEqual(documents.create_uid, user)
        self.assertEqual(len(documents._edi_get_installments()), 2)
        self.assertIn("40.00", str(documents.edi_payment_summary))
