# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import gzip
import re
import zipfile
from io import BytesIO
from types import SimpleNamespace
from unittest import mock

from xsdata.formats.dataclass.transports import DefaultTransport

from odoo import Command
from odoo.exceptions import UserError

from odoo.addons.l10n_br_nfe_dfe.tests.test_nfe_dfe import response_sucesso_individual

from ..hooks import uninstall_hook
from .common import KEY_1, KEY_2, DfeImportCase

NFE_NS = "http://www.portalfiscal.inf.br/nfe"


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


def _distribution_response(recipient):
    """The DF-e response of the NF-e KEY_1 addressed to ``recipient``."""

    def replace_recipient(match):
        xml = gzip.decompress(base64.b64decode(match.group(2)))
        xml = xml.replace(b"81493979000189", recipient.encode())
        return match.group(1) + base64.b64encode(gzip.compress(xml)).decode() + "</"

    return re.sub(
        r"(<docZip[^>]*>)([^<]+)</", replace_recipient, response_sucesso_individual
    ).encode()


class TestDfeImport(DfeImportCase):
    def test_xml_becomes_a_draft_document_without_creating_products(self):
        products = self.env["product.product"].search_count([])
        xml = self._xml(KEY_1)

        documents, errors = self.Document.dfe_import_files([("nfe.xml", xml)])

        self.assertFalse(errors)
        self.assertEqual(documents.state_edoc, "em_digitacao")
        self.assertEqual(documents.company_id, self.company)
        self.assertEqual(documents.import_state, "pending")
        self.assertEqual(base64.b64decode(documents.original_xml_file_id.datas), xml)
        line = documents.fiscal_line_ids
        self.assertEqual(line.name, "Brand new thing")
        self.assertEqual((line.quantity, line.price_unit), (1, 140))
        self.assertFalse(line.product_id)
        self.assertEqual(self.env["product.product"].search_count([]), products)

    def test_sending_the_same_file_again_opens_the_same_document(self):
        files = [("nfe.xml", self._xml(KEY_1))]
        first, _errors = self.Document.dfe_import_files(files)
        second, errors = self.Document.dfe_import_files(files)

        self.assertFalse(errors)
        self.assertEqual(first, second)

    def test_zip_with_two_notes_and_an_invalid_file(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("one.xml", self._xml(KEY_1))
            archive.writestr("two.xml", self._xml(KEY_2))
            archive.writestr("bad.xml", b"this is not an XML")

        documents, errors = self.Document.dfe_import_files(
            [("batch.zip", buffer.getvalue())]
        )

        self.assertEqual(len(documents), 2)
        self.assertEqual([name for name, _message in errors], ["batch.zip/bad.xml"])

    def test_cancelled_or_denied_by_the_protocol_is_refused(self):
        xml = self._xml(KEY_1).decode().split("?>", 1)[1]
        for status in ("101", "110"):
            protocol = (
                f'<protNFe versao="4.00"><infProt><chNFe>{KEY_1}</chNFe>'
                f"<cStat>{status}</cStat></infProt></protNFe>"
            )
            content = xml.replace("</NFe>", "</NFe>" + protocol)
            content = f'<nfeProc xmlns="{NFE_NS}" versao="4.00">{content}</nfeProc>'

            documents, errors = self.Document.dfe_import_files(
                [("nfe.xml", content.encode())]
            )

            self.assertFalse(documents, status)
            self.assertEqual(len(errors), 1, status)

    def test_recipient_that_is_not_a_company_of_the_database_is_refused(self):
        xml = self._xml(KEY_1, recipient="11222333000181")

        documents, errors = self.Document.dfe_import_files([("nfe.xml", xml)])

        self.assertFalse(documents)
        self.assertIn("not a company", errors[0][1])

    def test_note_goes_to_the_company_of_the_recipient(self):
        xml = self._xml(
            KEY_1, recipient=self.other_company.partner_id.cnpj_cpf_stripped
        )

        documents, _errors = self.Document.dfe_import_files([("nfe.xml", xml)])

        self.assertEqual(documents.company_id, self.other_company)

    def test_access_key_with_the_complete_xml_in_the_inbox(self):
        self._dfe_document(KEY_1, summary_only=False)
        wizard = self.env["l10n_br_fiscal_dfe_import.wizard"].create(
            {"access_key": KEY_1}
        )

        action = wizard.action_import()

        self.assertEqual(action["res_id"], self._imported(KEY_1).id)

    def test_access_key_with_only_the_summary_asks_to_acknowledge(self):
        dfe_document = self._dfe_document(KEY_1)
        wizard = self.env["l10n_br_fiscal_dfe_import.wizard"].create(
            {"access_key": KEY_1}
        )

        action = wizard.action_import()

        self.assertEqual(action["res_id"], wizard.id)
        self.assertEqual(wizard.state, "confirm")
        self.assertFalse(dfe_document.manifestations_ids)

        event_model = type(self.env["l10n_br_nfe.md_event"])
        with mock.patch.object(
            event_model, "_get_processor", return_value=_acknowledgement_processor()
        ):
            wizard.action_confirm_acknowledgement()

        self.assertEqual(dfe_document.manifestations_ids.event_type, "ciente")
        self.assertEqual(dfe_document.manifestations_ids.state, "done")
        self.assertEqual(dfe_document.import_requested_user_id, self.env.user)
        self.assertFalse(self._imported(KEY_1))

    @mock.patch.object(DefaultTransport, "post")
    def test_document_is_created_when_the_complete_xml_arrives(self, mock_post):
        company = self.env.ref("l10n_br_base.empresa_lucro_presumido")
        dfe_document = self._dfe_document(KEY_1)
        dfe_document.write(
            {"company_id": company.id, "import_requested_user_id": self.env.user.id}
        )
        recipient = company.partner_id.cnpj_cpf_stripped
        mock_post.return_value = _distribution_response(recipient)

        company.nfe_dfe_search_documents()

        self.assertTrue(self._imported(KEY_1, company))
        self.assertFalse(dfe_document.import_requested_user_id)

    def test_acknowledgement_after_ten_days_asks_for_the_file(self):
        self._dfe_document(KEY_1, days=30)
        wizard = self.env["l10n_br_fiscal_dfe_import.wizard"].create(
            {"access_key": KEY_1}
        )

        with self.assertRaisesRegex(UserError, "Upload the XML file"):
            wizard.action_import()

    def test_wizard_opens_the_document_or_the_list(self):
        wizard = self.env["l10n_br_fiscal_dfe_import.wizard"]
        attachments = [
            self.env["ir.attachment"].create(
                {"name": f"{key}.xml", "raw": self._xml(key)}
            )
            for key in (KEY_1, KEY_2)
        ]

        single = wizard.create(
            {"attachment_ids": [Command.set(attachments[0].ids)]}
        ).action_import()
        both = wizard.create(
            {"attachment_ids": [Command.set([a.id for a in attachments])]}
        ).action_import()

        self.assertEqual(single["view_mode"], "form")
        self.assertEqual(len(both["domain"][0][2]), 2)

    def test_uninstall_gives_the_menus_back_to_the_original_actions(self):
        uninstall_hook(self.env.cr, None)

        menu = self.env.ref("l10n_br_nfe.nfe_import_document")
        self.assertEqual(
            menu.action, self.env.ref("l10n_br_nfe.l10n_br_nfe_import_xml_action")
        )
