# Copyright (C) 2023 - TODAY Felipe Zago - KMEE
# Copyright 2026 Engenere (<https://engenere.one>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import base64
import gzip
import re
import zipfile
from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace
from unittest import mock

from xsdata.formats.dataclass.transports import DefaultTransport

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from .test_nfe_dfe import (
    response_sucesso_individual,
    response_sucesso_multiplos,
)

KEY_FIXTURE = "35200159594315000157550010000000012062777161"
KEY = "35200159594315000157550010000000992062777167"


def _distribution_response(recipient):
    """The DF-e response with the NF-e of ``KEY`` addressed to ``recipient``.

    The key is another one, because the module has a demo document with the key
    of the fixture."""

    def replace_recipient(match):
        xml = gzip.decompress(base64.b64decode(match.group(2)))
        xml = xml.replace(b"81493979000189", recipient.encode())
        xml = xml.replace(KEY_FIXTURE.encode(), KEY.encode())
        xml = xml.replace(b"<nNF>1</nNF>", b"<nNF>99</nNF>")
        return match.group(1) + base64.b64encode(gzip.compress(xml)).decode() + "</"

    return re.sub(
        r"(<docZip[^>]*>)([^<]+)</", replace_recipient, response_sucesso_individual
    ).encode()


def _acknowledgement_processor():
    event = SimpleNamespace(
        cStat="135",
        xMotivo="ok",
        nProt="1",
        dhRegEvento="2026-11-18T10:00:00-03:00",
    )
    answer = SimpleNamespace(
        retorno=SimpleNamespace(status_code=200, _content=b"<ok/>"),
        resposta=SimpleNamespace(retEvento=[SimpleNamespace(infEvento=event)]),
    )
    return SimpleNamespace(ciencia_da_operacao=lambda key, cnpj: answer)


def _bytes(string):
    return string.encode("utf-8") if isinstance(string, str) else string


class TestNFeDFe(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")

    def _search_dfe(self):
        return self.env["l10n_br_fiscal_dfe.dfe"].search(
            [("company_id", "=", self.company.id)]
        )

    @mock.patch.object(DefaultTransport, "post")
    def test_download_document_proc_nfe(self, _mock_post):
        _mock_post.return_value = _distribution_response(self._recipient())

        self.company.nfe_dfe_search_documents()
        dfe_docs = self.env["l10n_br_fiscal_dfe.document"].search(
            [("company_id", "=", self.company.id)]
        )

        access_key = KEY
        for doc in dfe_docs.with_context(allowed_company_ids=self.company.ids):
            action = doc.import_document()
            self.assertEqual(action["res_model"], "l10n_br_fiscal.document")

        self.assertEqual(len(self._search_dfe()), 1)
        fiscal_doc = self.env["l10n_br_fiscal.document"].search(
            [("document_key", "=", access_key)], limit=1
        )
        self.assertTrue(fiscal_doc, "Fiscal document should be created after import")
        self.assertTrue(fiscal_doc.imported_document)
        self.assertEqual(action["res_id"], fiscal_doc.id)
        self.assertEqual(_mock_post.call_count, 1)

        imported_dfe = dfe_docs.filtered(lambda d: d.access_key == access_key)
        self.assertEqual(imported_dfe.fiscal_document_id, fiscal_doc)

        # Nothing was billed yet, so the button opens the fiscal document.
        action = imported_dfe.action_view_imported_document()
        self.assertEqual(action["res_model"], "l10n_br_fiscal.document")
        self.assertEqual(action["res_id"], fiscal_doc.id)

    def _recipient(self):
        return self.company.partner_id.cnpj_cpf_stripped

    @mock.patch.object(DefaultTransport, "post")
    def test_search_dfe_success(self, _mock_post):
        _mock_post.return_value = _bytes(response_sucesso_multiplos)

        self.company.nfe_dfe_search_documents()
        dfe_records = self._search_dfe()
        self.assertTrue(dfe_records)

        dfe_sorted = dfe_records.sorted(lambda record: record.nsu or "")
        dfe1, dfe2 = dfe_sorted

        self.assertEqual(dfe1.company_id, self.company)
        self.assertEqual(
            dfe1.access_key, "31201010588201000105550010038421171838422178"
        )
        self.assertEqual(dfe1.document_type_dfe, "summary")
        self.assertEqual(dfe1.nsu, "000000000000200")
        self.assertEqual(
            dfe1.display_name,
            "31201010588201000105550010038421171838422178 - Summary",
        )
        self.assertEqual(dfe1.dfe_document_id.color_status, "blue")
        self.assertEqual(dfe1.dfe_document_id.emitter, "ZAP GRAFICA E EDITORA EIRELI")
        self.assertEqual(dfe1.dfe_document_id.vat, "10.588.201/0001-05")
        self.assertEqual(
            dfe1.dfe_document_id.display_name,
            "31201010588201000105550010038421171838422178",
        )
        self.assertEqual(
            dfe1.dfe_document_id.access_key,
            "31201010588201000105550010038421171838422178",
        )

        self.assertEqual(dfe2.company_id, self.company)
        self.assertEqual(
            dfe2.access_key, "35200159594315000157550010000000012062777161"
        )
        self.assertEqual(dfe2.document_type_dfe, "complete")
        self.assertEqual(dfe2.dfe_document_id.emitter, "TESTE - Simples Nacional")
        self.assertEqual(dfe2.dfe_document_id.document_amount, 14.0)
        self.assertEqual(dfe2.dfe_document_id.vat, "59.594.315/0001-57")
        self.assertEqual(
            dfe2.dfe_document_id.access_key,
            "35200159594315000157550010000000012062777161",
        )
        self.assertEqual(
            dfe2.display_name,
            "35200159594315000157550010000000012062777161 - Complete",
        )
        self.assertEqual(dfe2.dfe_document_id.color_status, "green")
        self.assertEqual(
            dfe2.dfe_document_id.display_name,
            "35200159594315000157550010000000012062777161",
        )

    @mock.patch.object(DefaultTransport, "post")
    def test_generate_danfe(self, _mock_post):
        _mock_post.return_value = _bytes(response_sucesso_individual)
        self.company.nfe_dfe_search_documents()
        dfe_record = self._search_dfe()[0]

        result = dfe_record.dfe_document_id.make_pdf()

        self.assertEqual(result["type"], "ir.actions.act_url")
        self.assertTrue(result["url"].startswith("/web/content/"))
        self.assertIn("download=true", result["url"])

    @mock.patch.object(DefaultTransport, "post")
    def test_download_documents(self, _mock_post):
        _mock_post.return_value = _bytes(response_sucesso_multiplos)

        self.company.nfe_dfe_search_documents()
        dfe_sorted = self._search_dfe().sorted(lambda record: record.nsu or "")
        dfe1, dfe2 = dfe_sorted

        attachment_2 = self.env["ir.attachment"].search(
            [("res_id", "=", dfe2.id), ("res_model", "=", "l10n_br_fiscal_dfe.dfe")]
        )
        self.assertTrue(attachment_2)

        result_dfe1 = dfe1.action_download_xml()
        attachment_single_dfe1 = self._get_attachment_from_result(result_dfe1)
        self.assertTrue(attachment_single_dfe1)
        self.assertEqual(attachment_single_dfe1, dfe1.attachment_id)

        result_dfe2_access_key = dfe2.dfe_document_id.action_download_xml()
        attachment_single_dfe2_access_key = self._get_attachment_from_result(
            result_dfe2_access_key
        )
        self.assertTrue(attachment_single_dfe2_access_key)
        with self.assertRaises(UserError):
            dfe1.dfe_document_id.action_download_xml()

    def _get_attachment_from_result(self, result):
        _, _, _, att_id, _ = result["url"].split("/")
        return self.env["ir.attachment"].browse(int(att_id))

    @mock.patch.object(DefaultTransport, "post")
    def test_download_xmls_zip_success(self, _mock_post):
        """Zip download with complete NF-e documents should return a valid zip."""
        _mock_post.return_value = _bytes(response_sucesso_multiplos)
        self.company.nfe_dfe_search_documents()

        dfe_docs = self.env["l10n_br_fiscal_dfe.document"].search(
            [("company_id", "=", self.company.id)]
        )
        # Filter only documents that have a complete DFe
        docs_with_complete = dfe_docs.filtered(
            lambda d: any(r.document_type_dfe == "complete" for r in d.dfe_ids)
        )
        self.assertTrue(docs_with_complete)

        result = docs_with_complete.action_download_xmls_zip()

        self.assertEqual(result["type"], "ir.actions.act_url")
        self.assertIn("download=true", result["url"])
        self.assertIn("dfe_xmls.zip", result["url"])

        # Verify zip content
        att_id = int(result["url"].split("/")[3])
        attachment = self.env["ir.attachment"].browse(att_id)
        zip_data = base64.b64decode(attachment.with_context(bin_size=False).datas)
        with zipfile.ZipFile(BytesIO(zip_data), "r") as zf:
            self.assertTrue(zf.namelist(), "Zip should contain at least one file")
            for name in zf.namelist():
                self.assertTrue(name.endswith(".xml"))

    @mock.patch.object(DefaultTransport, "post")
    def test_download_xmls_zip_no_complete(self, _mock_post):
        """Zip download with only summary documents should raise UserError."""
        _mock_post.return_value = _bytes(response_sucesso_multiplos)
        self.company.nfe_dfe_search_documents()

        dfe_docs = self.env["l10n_br_fiscal_dfe.document"].search(
            [("company_id", "=", self.company.id)]
        )
        # Keep only documents without complete DFe
        docs_summary_only = dfe_docs.filtered(
            lambda d: not any(r.document_type_dfe == "complete" for r in d.dfe_ids)
        )
        self.assertTrue(docs_summary_only, "Should have at least one summary-only doc")

        with self.assertRaises(UserError):
            docs_summary_only.action_download_xmls_zip()


class TestNFeDFeImportByKey(TransactionCase):
    """The key of a note that only has the summary: the acknowledgement that
    releases the XML, and the document that is created when the XML arrives."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.env = cls.env(
            context=dict(cls.env.context, allowed_company_ids=cls.company.ids)
        )
        cls.Wizard = cls.env["l10n_br_fiscal_edi.document.import.wizard"]
        cls.event_model = type(cls.env["l10n_br_nfe.md_event"])

    def _summary(self, days=0):
        dfe_document = self.env["l10n_br_fiscal_dfe.document"].create(
            {
                "access_key": KEY,
                "company_id": self.company.id,
                "fiscal_type": "nfe",
                "document_state": "1",
                "document_emission_date": fields.Datetime.now() - timedelta(days=days),
            }
        )
        self.env["l10n_br_fiscal_dfe.dfe"].create(
            {
                "access_key": KEY,
                "company_id": self.company.id,
                "fiscal_type": "nfe",
                "dfe_document_id": dfe_document.id,
                "document_type_dfe": "summary",
            }
        )
        return dfe_document

    def _imported(self):
        return self.env["l10n_br_fiscal.document"].search(
            [("document_key", "=", KEY), ("company_id", "=", self.company.id)]
        )

    def _acknowledge(self, wizard):
        with mock.patch.object(
            self.event_model,
            "_get_processor",
            return_value=_acknowledgement_processor(),
        ):
            return wizard.action_confirm_request()

    def _fiscal_user(self):
        return self.env["res.users"].create(
            {
                "name": "Fiscal importer",
                "login": "nfe_dfe_importer",
                "email": "nfe_dfe_importer@example.com",
                "company_id": self.company.id,
                "company_ids": [Command.set(self.company.ids)],
                "groups_id": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("l10n_br_fiscal.group_user").id,
                        ]
                    )
                ],
            }
        )

    def test_the_summary_asks_to_acknowledge_before_the_xml_is_requested(self):
        dfe_document = self._summary()

        action = dfe_document.import_document()

        wizard = self.Wizard.browse(action["res_id"])
        self.assertEqual(wizard.state, "confirm")
        self.assertIn("ciencia", wizard.confirm_message)
        self.assertFalse(dfe_document.manifestations_ids)
        self._acknowledge(wizard)
        self.assertEqual(dfe_document.manifestations_ids.event_type, "ciente")
        self.assertEqual(dfe_document.manifestations_ids.state, "done")
        self.assertEqual(dfe_document.import_requested_user_id, self.env.user)
        self.assertIn("Acknowledgement", dfe_document.message_ids[0].body)
        self.assertFalse(self._imported())

    @mock.patch.object(DefaultTransport, "post")
    def test_the_document_is_created_when_the_complete_xml_arrives(self, mock_post):
        user = self._fiscal_user()
        dfe_document = self._summary()
        dfe_document.import_requested_user_id = user
        mock_post.return_value = _distribution_response(
            self.company.partner_id.cnpj_cpf_stripped
        )

        self.company.nfe_dfe_search_documents()

        document = self._imported()
        self.assertTrue(document)
        self.assertEqual(document.create_uid, user)
        self.assertFalse(dfe_document.import_requested_user_id)
        self.assertEqual(document.activity_ids.user_id, user)

    def test_the_acknowledgement_after_ten_days_asks_for_the_file(self):
        dfe_document = self._summary(days=30)

        with self.assertRaisesRegex(UserError, "Upload the XML file"):
            dfe_document.import_document()

        self.assertFalse(dfe_document.manifestations_ids)

    def test_a_note_already_acknowledged_only_registers_the_request(self):
        dfe_document = self._summary()
        self.env["l10n_br_nfe.md_event"].create(
            {
                "access_key": KEY,
                "event_type": "ciente",
                "state": "done",
                "company_id": self.company.id,
                "dfe_document_id": dfe_document.id,
            }
        )

        action = dfe_document.import_document()

        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(len(dfe_document.manifestations_ids), 1)
        self.assertEqual(dfe_document.import_requested_user_id, self.env.user)

    def test_common_fiscal_user_acknowledges_as_the_author(self):
        user = self._fiscal_user()
        dfe_document = self._summary()
        wizard = self.Wizard.with_user(user).browse(
            dfe_document.with_user(user).import_document()["res_id"]
        )

        self._acknowledge(wizard)

        self.assertEqual(dfe_document.manifestations_ids.create_uid, user)
        self.assertEqual(dfe_document.import_requested_user_id, user)
