# Copyright 2026 Engenere.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import base64
import zipfile
from io import BytesIO
from unittest import mock

from xsdata.formats.dataclass.transports import DefaultTransport

from odoo import Command
from odoo.tests.common import TransactionCase, tagged

from .common import CTE_ACCESS_KEY, response_cte_only


class TestCteDfeImport(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.company.cte_dfe_next_query = False
        # l10n_br_cte demo/tests may leave a fiscal document with this key
        cls.env["l10n_br_fiscal.document"].search(
            [("document_key", "=", CTE_ACCESS_KEY)]
        ).unlink()

    def _fetch_document(self, mock_post):
        mock_post.return_value = response_cte_only()
        self.company.cte_dfe_search_documents()
        return self.env["l10n_br_fiscal_dfe.document"].search(
            [("company_id", "=", self.company.id), ("fiscal_type", "=", "cte")]
        )

    @mock.patch.object(DefaultTransport, "post")
    def test_import_cte(self, mock_post):
        document = self._fetch_document(mock_post)
        self.assertFalse(document.fiscal_document_id)

        # the generic import of the inbox reads the complete DF-e XML with the reader
        # of l10n_br_cte
        # the web client reads the sizes of the binary fields (bin_size): the XML
        # is read as content all the same
        action = document.with_context(bin_size=True).import_document()
        self.assertEqual(action["res_model"], "l10n_br_fiscal.document")
        fiscal_document = self.env["l10n_br_fiscal.document"].search(
            [("document_key", "=", CTE_ACCESS_KEY)], limit=1
        )
        self.assertEqual(action["res_id"], fiscal_document.id)
        self.assertEqual(fiscal_document.document_type_id.code, "57")
        # the CT-e of the fixture is issued by a company of the database: the reader
        # imports it as a document of that company, an output
        self.assertEqual(fiscal_document.fiscal_operation_type, "out")
        self.assertEqual(fiscal_document.issuer, "company")
        self.assertTrue(fiscal_document.imported_document)
        # non-stored compute read before the import: drop the cached value
        document.invalidate_recordset(["fiscal_document_id"])
        self.assertEqual(document.fiscal_document_id, fiscal_document)

        action = document.action_view_imported_document()
        self.assertEqual(action["res_model"], "l10n_br_fiscal.document")
        self.assertEqual(action["res_id"], fiscal_document.id)

    @mock.patch.object(DefaultTransport, "post")
    def test_generate_dacte(self, mock_post):
        document = self._fetch_document(mock_post)

        result = document.make_pdf()

        self.assertEqual(result["type"], "ir.actions.act_url")
        self.assertIn("download=true", result["url"])
        attachment_id = int(result["url"].split("/")[3].split("?")[0])
        attachment = self.env["ir.attachment"].browse(attachment_id)
        self.assertEqual(attachment.name, f"DACTE_{CTE_ACCESS_KEY}.pdf")
        pdf = base64.b64decode(attachment.with_context(bin_size=False).datas)
        self.assertTrue(pdf.startswith(b"%PDF"))

    @mock.patch.object(DefaultTransport, "post")
    def test_download_xml_and_zip(self, mock_post):
        document = self._fetch_document(mock_post)

        result = document.action_download_xml()
        self.assertIn(f"procCTe_{CTE_ACCESS_KEY}.xml", result["url"])

        result = document.action_download_xmls_zip()
        attachment = self.env["ir.attachment"].browse(int(result["url"].split("/")[3]))
        zip_data = base64.b64decode(attachment.with_context(bin_size=False).datas)
        with zipfile.ZipFile(BytesIO(zip_data)) as zf:
            self.assertEqual(zf.namelist(), [f"procCTe_{CTE_ACCESS_KEY}.xml"])
            self.assertIn(b"<cteProc", zf.read(zf.namelist()[0]))


@tagged("post_install", "-at_install")
class TestCteDfeImportedDocumentAccess(TransactionCase):
    """Accounting is loaded after this module: the move exists only post install."""

    @mock.patch.object(DefaultTransport, "post")
    def test_a_pure_fiscal_user_opens_the_imported_document_from_the_inbox(
        self, mock_post
    ):
        company = self.env.ref("l10n_br_base.empresa_lucro_presumido")
        company.cte_dfe_next_query = False
        self.env["l10n_br_fiscal.document"].search(
            [("document_key", "=", CTE_ACCESS_KEY)]
        ).unlink()
        mock_post.return_value = response_cte_only()
        company.cte_dfe_search_documents()
        record = self.env["l10n_br_fiscal_dfe.document"].search(
            [("company_id", "=", company.id), ("fiscal_type", "=", "cte")], limit=1
        )
        # the CT-e of the fixture is issued by "Empresa Simples Nacional" and
        # addressed to the lucro presumido one: the reader takes the first of them
        # that the database has, and the user has both
        companies = company | self.env.ref("l10n_br_base.empresa_simples_nacional")
        user = self.env["res.users"].create(
            {
                "name": "Pure fiscal",
                "login": "cte_dfe_pure_fiscal",
                "company_id": company.id,
                "company_ids": [Command.set(companies.ids)],
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
        record = record.with_user(user).with_context(allowed_company_ids=companies.ids)
        record.with_context(bin_size=True).import_document()
        if "move_ids" not in record.fiscal_document_id._fields:
            self.skipTest("No accounting")
        # An invoice of the import: accounting is not for a fiscal user.
        journal = (
            self.env["account.journal"]
            .sudo()
            .search(
                [("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1
            )
        )
        move = (
            self.env["account.move"]
            .sudo()
            .create(
                {
                    "move_type": "in_invoice",
                    "company_id": company.id,
                    # the journal of the company of the note, not the one by default
                    "journal_id": journal.id,
                    "partner_id": record.fiscal_document_id.partner_id.id,
                    "fiscal_document_id": record.fiscal_document_id.id,
                }
            )
        )
        self.assertEqual(record.fiscal_document_id.sudo().move_ids, move)
        self.env.flush_all()
        self.env.invalidate_all()

        action = record.action_view_imported_document()

        self.assertEqual(action["res_model"], "l10n_br_fiscal.document")
        # whoever has accounting rights is taken to the document as well, the
        # invoice has its own button
        self.assertEqual(
            record.sudo().action_view_imported_document()["res_model"],
            "l10n_br_fiscal.document",
        )
        document = (
            self.env[action["res_model"]]
            .with_user(user)
            .with_context(**action["context"])
            .browse(action["res_id"])
        )
        self.assertEqual(document, record.fiscal_document_id)
        view = document.get_view(view_type="form")
        names = [name for name in document._fields if f'name="{name}"' in view["arch"]]
        self.assertTrue(names)
        document.read(names)
