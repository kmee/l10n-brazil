# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import gzip
import re
import zipfile
from io import BytesIO
from types import SimpleNamespace
from unittest import mock

from lxml import etree
from xsdata.formats.dataclass.transports import DefaultTransport

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.modules import get_module_resource
from odoo.tools import file_open
from odoo.tools.translate import TranslationFileReader

from odoo.addons.l10n_br_nfe_dfe.tests.test_nfe_dfe import response_sucesso_individual

from ..hooks import uninstall_hook
from .common import KEY_1, KEY_2, KEY_3, DfeImportCase

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
        self.assertIn("Acknowledgement", dfe_document.message_ids[0].body)
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

        self.assert_window_action(single)
        self.assert_window_action(both)
        self.assertEqual(single["view_mode"], "form")
        self.assertEqual(len(both["domain"][0][2]), 2)

    def test_returned_actions_are_complete_with_the_errors_of_a_batch(self):
        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("one.xml", self._xml(KEY_1))
            archive.writestr("bad.xml", b"this is not an XML")
        attachment = self.env["ir.attachment"].create(
            {"name": "batch.zip", "raw": buffer.getvalue()}
        )
        wizard = self.env["l10n_br_fiscal_dfe_import.wizard"].create(
            {"attachment_ids": [Command.set(attachment.ids)]}
        )

        notification = wizard.action_import()

        self.assertEqual(notification["tag"], "display_notification")
        self.assertIn("bad.xml", notification["params"]["message"])
        self.assertTrue(notification["params"]["sticky"])
        self.assert_window_action(notification["params"]["next"])

    def test_confirmation_dialog_action_is_complete(self):
        self._dfe_document(KEY_1)
        wizard = self.env["l10n_br_fiscal_dfe_import.wizard"].create(
            {"access_key": KEY_1}
        )

        self.assert_window_action(wizard.action_import())

    def test_uninstall_gives_the_menus_back_to_the_original_actions(self):
        uninstall_hook(self.env.cr, None)

        menu = self.env.ref("l10n_br_nfe.nfe_import_document")
        self.assertEqual(
            menu.action, self.env.ref("l10n_br_nfe.l10n_br_nfe_import_xml_action")
        )

    def test_unknown_ncm_is_kept_as_declared_and_not_created(self):
        ncm = self.env["l10n_br_fiscal.ncm"].search_count([])
        xml = self._xml(
            KEY_1, replace=[(b"<NCM>94033000</NCM>", b"<NCM>99999999</NCM>")]
        )

        documents, errors = self.Document.dfe_import_files([("nfe.xml", xml)])

        line = documents.fiscal_line_ids
        self.assertFalse(errors)
        self.assertEqual(line.import_ncm_code, "99999999")
        self.assertFalse(line.ncm_id)
        self.assertIn("99999999", documents.import_warning)
        self.assertEqual(self.env["l10n_br_fiscal.ncm"].search_count([]), ncm)

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

        documents, errors = self.Document.dfe_import_files([("nfe.xml", xml)])

        self.assertFalse(errors)
        self.assertTrue(documents)
        self.assertEqual(counts, [self.env[model].search_count([]) for model in models])

    def test_partners_created_by_the_import_are_logged(self):
        carrier = (
            b"<modFrete>0</modFrete><transporta><CNPJ>11222333000181</CNPJ>"
            b"<xNome>Transp Nova</xNome></transporta>"
        )
        xml = self._xml(KEY_1, replace=[(b"<modFrete>9</modFrete>", carrier)])

        documents, _errors = self.Document.dfe_import_files([("nfe.xml", xml)])

        self.assertIn("Transp Nova", "".join(documents.message_ids.mapped("body")))

    def test_unexpected_error_is_reported_without_the_raw_message(self):
        model = type(self.Document)
        with mock.patch.object(
            model, "import_binding_nfe", side_effect=RuntimeError("raw boom")
        ):
            _documents, errors = self.Document.dfe_import_files(
                [("nfe.xml", self._xml(KEY_1))]
            )

        self.assertIn("unexpected error", errors[0][1])
        self.assertNotIn("raw boom", errors[0][1])

    def test_failed_import_from_the_inbox_warns_who_asked(self):
        dfe_document = self._dfe_document(
            KEY_1, summary_only=False, recipient="11222333000181"
        )
        dfe_document.import_requested_user_id = self.env.user

        dfe_document._dfe_import_requested_xml()

        activity = dfe_document.activity_ids
        self.assertEqual(activity.user_id, self.env.user)
        self.assertIn("not a company", activity.note)

    def _manager_of(self, companies):
        return self.env["res.users"].create(
            {
                "name": "Importer",
                "login": "dfe_importer_%s" % len(companies),
                "company_id": companies[0].id,
                "company_ids": [Command.set(companies.ids)],
                "groups_id": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("base.group_partner_manager").id,
                            self.env.ref("l10n_br_fiscal.group_manager").id,
                            self.env.ref("l10n_br_nfe.group_manager").id,
                        ]
                    )
                ],
            }
        )

    def test_note_of_another_company_opens_in_the_context_of_its_company(self):
        user = self._manager_of(self.company | self.other_company)
        wizard = self.env["l10n_br_fiscal_dfe_import.wizard"].with_user(user)
        wizard = wizard.with_context(
            allowed_company_ids=[self.company.id, self.other_company.id]
        )
        attachment = self.env["ir.attachment"].create(
            {"name": "nfe.xml", "raw": self._other_company_xml(KEY_1)}
        )

        action = wizard.create(
            {"attachment_ids": [Command.set(attachment.ids)]}
        ).action_import()

        self.assertIn(self.other_company.id, action["context"]["allowed_company_ids"])
        document = self.Document.browse(action["res_id"])
        self.assertEqual(document.company_id, self.other_company)

    def test_repeated_note_of_another_company_opens_the_existing_document(self):
        user = self._manager_of(self.company | self.other_company)
        service = self.Document.with_user(user).with_context(
            allowed_company_ids=[self.company.id, self.other_company.id]
        )
        files = [("nfe.xml", self._other_company_xml(KEY_1))]
        first, _errors = service.dfe_import_files(files)

        second, errors = service.dfe_import_files(files)

        self.assertFalse(errors)
        self.assertEqual(first, second)

    def test_note_of_a_company_the_user_cannot_access_is_refused(self):
        user = self._manager_of(self.company)
        service = self.Document.with_user(user)

        documents, errors = service.dfe_import_files(
            [("nfe.xml", self._other_company_xml(KEY_1))]
        )

        self.assertFalse(documents)
        self.assertIn("no access to the company", errors[0][1])

    def _other_company_xml(self, key):
        return self._xml(key, recipient=self.other_company.partner_id.cnpj_cpf_stripped)

    def test_confirmation_text_uses_the_full_width_of_the_dialog(self):
        arch = self.env["l10n_br_fiscal_dfe_import.wizard"].get_view(view_type="form")
        form = etree.fromstring(arch["arch"])

        message = form.xpath("//field[@name='confirm_message']")[0]

        self.assertFalse(message.xpath("ancestor::group"))

    def test_document_born_from_the_inbox_is_recorded_in_both_histories(self):
        dfe_document = self._dfe_document(KEY_1, summary_only=False)
        dfe_document.import_requested_user_id = self.env.user

        dfe_document._dfe_import_requested_xml()

        document = self._imported(KEY_1)
        self.assertIn(KEY_1, document.message_ids[0].body)
        self.assertIn("created", dfe_document.message_ids[0].body)

    def test_unknown_cfop_is_not_created_and_does_not_break_the_import(self):
        cfop = self.env["l10n_br_fiscal.cfop"].search_count([])
        xml = self._xml(KEY_1, replace=[(b"<CFOP>5102</CFOP>", b"<CFOP>5999</CFOP>")])

        documents, errors = self.Document.dfe_import_files([("nfe.xml", xml)])

        self.assertFalse(errors)
        self.assertTrue(documents)
        self.assertEqual(self.env["l10n_br_fiscal.cfop"].search_count([]), cfop)

    def test_operation_is_suggested_without_touching_the_values_of_the_file(self):
        documents, _errors = self.Document.dfe_import_files(
            [("nfe.xml", self._xml(KEY_1))]
        )

        line = documents.fiscal_line_ids
        operation = self.env.ref("l10n_br_fiscal.fo_compras")
        self.assertEqual(documents.fiscal_operation_id, operation)
        self.assertEqual(line.fiscal_operation_id, operation)
        self.assertEqual(line.cfop_id.code, "1102")
        self.assertEqual(line.partner_cfop_id.code, "5102")
        self.assertEqual((line.quantity, line.price_unit), (1, 140))
        self.assertEqual(documents.fiscal_amount_total, 140)
        self.assertEqual(documents.fiscal_amount_untaxed, 140)
        self.assertNotIn("fiscal operation", documents.import_warning or "")

    def test_without_a_matching_operation_the_document_says_what_to_choose(self):
        xml = self._xml(KEY_1, replace=[(b"<CFOP>5102</CFOP>", b"<CFOP>5999</CFOP>")])

        documents, errors = self.Document.dfe_import_files([("nfe.xml", xml)])

        self.assertFalse(errors)
        self.assertFalse(documents.fiscal_operation_id)
        self.assertIn("fiscal operation", documents.import_warning)

    def test_imported_documents_list_shows_the_review_state(self):
        action = self.env.ref("l10n_br_fiscal_dfe_import.imported_document_dfe_action")
        arch = self.Document.get_view(action.view_id.id, "tree")["arch"]

        self.assertTrue(etree.fromstring(arch).xpath("//field[@name='import_state']"))

    def test_list_of_several_documents_uses_the_same_view(self):
        view = self.env.ref("l10n_br_fiscal_dfe_import.document_import_tree")
        wizard = self.env["l10n_br_fiscal_dfe_import.wizard"]
        documents, _errors = self.Document.dfe_import_files(
            [("one.xml", self._xml(KEY_1)), ("two.xml", self._xml(KEY_2))]
        )

        action = wizard._documents_action(documents)

        self.assertEqual(action["views"][0], (view.id, "tree"))

    def test_pt_br_translation_is_complete(self):
        path = get_module_resource("l10n_br_fiscal_dfe_import", "i18n", "pt_BR.po")
        with file_open(path, "rb") as po_file:
            terms = list(TranslationFileReader(po_file, fileformat="po"))

        self.assertFalse([term["src"] for term in terms if not term["value"]])
        self.assertIn("Review", [term["src"] for term in terms])

    def test_unknown_unit_stays_empty_and_is_kept_as_declared(self):
        uom = self.env["uom.uom"].search_count([])
        xml = self._xml(
            KEY_1,
            replace=[(b"<uCom>UN</uCom>", b"<uCom>ZZZ</uCom>")],
        )

        documents, errors = self.Document.dfe_import_files([("nfe.xml", xml)])

        line = documents.fiscal_line_ids
        self.assertFalse(errors)
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

        documents, _errors = self.Document.dfe_import_files([("nfe.xml", xml)])

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

        documents, _errors = self.Document.dfe_import_files([("nfe.xml", xml)])

        line = documents.fiscal_line_ids
        self.assertTrue(line.product_id)
        self.assertEqual(line.import_state, "pending")

    def _fiscal_user(self):
        return self.env["res.users"].create(
            {
                "name": "Fiscal only",
                "login": "dfe_fiscal_only",
                "groups_id": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("l10n_br_fiscal.group_manager").id,
                        ]
                    )
                ],
            }
        )

    def test_fiscal_user_without_the_nfe_group_cannot_open_the_window(self):
        user = self._fiscal_user()
        menu = self.env.ref("l10n_br_nfe.nfe_import_document")

        with self.assertRaises(AccessError):
            self.env["l10n_br_fiscal_dfe_import.wizard"].with_user(user).create({})
        self.assertFalse(menu.with_user(user)._filter_visible_menus())

    def test_nfe_manager_sees_the_menu_and_opens_the_window(self):
        user = self._manager_of(self.company)
        menu = self.env.ref("l10n_br_nfe.nfe_import_document")

        wizard = self.env["l10n_br_fiscal_dfe_import.wizard"].with_user(user)
        wizard = wizard.with_context(allowed_company_ids=[self.company.id])

        self.assertTrue(wizard.create({}))
        self.assertTrue(menu.with_user(user)._filter_visible_menus())

    def test_uninstall_gives_the_menu_back_to_the_fiscal_manager_group(self):
        uninstall_hook(self.env.cr, None)

        menu = self.env.ref("l10n_br_nfe.nfe_import_document")
        self.assertEqual(menu.groups_id, self.env.ref("l10n_br_fiscal.group_manager"))

    def test_note_of_a_company_not_selected_in_the_switcher_is_refused(self):
        user = self._manager_of(self.company | self.other_company)
        service = self.Document.with_user(user).with_context(
            allowed_company_ids=[self.company.id]
        )
        files = [
            ("other.xml", self._other_company_xml(KEY_1)),
            ("mine.xml", self._xml(KEY_2)),
        ]

        documents, errors = service.dfe_import_files(files)

        self.assertEqual(documents.company_id, self.company)
        self.assertEqual([name for name, _message in errors], ["other.xml"])
        self.assertIn(self.other_company.name, errors[0][1])
        self.assertFalse(self._imported(KEY_1, self.other_company))

    def test_no_warning_leaves_the_field_unset_so_the_banner_stays_hidden(self):
        documents, _errors = self.Document.dfe_import_files(
            [("nfe.xml", self._xml(KEY_1))]
        )

        self.assertIs(documents.import_warning, False)
        self.assertNotIn("fiscal operation", documents.import_warning or "")

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

    @property
    def uom_unit(self):
        return self.env.ref("uom.product_uom_unit")

    def test_product_mapped_for_the_same_supplier_enters_resolved(self):
        product = self._supplier_product()

        documents, _errors = self.Document.dfe_import_files(
            [("nfe.xml", self._depara_note(KEY_2))]
        )

        line = documents.fiscal_line_ids
        self.assertEqual(line.product_id, product)
        self.assertEqual(line.import_state, "resolved")

    def test_product_found_by_internal_code_is_only_a_suggestion(self):
        product = self.env["product.product"].create(
            {"name": "Same code", "default_code": "ZZ-NEW-1"}
        )
        infos = self.env["product.supplierinfo"].search_count([])

        documents, _errors = self.Document.dfe_import_files(
            [("nfe.xml", self._depara_note(KEY_2))]
        )

        line = documents.fiscal_line_ids
        self.assertEqual(line.product_id, product)
        self.assertEqual(line.import_state, "matched")
        self.assertEqual(self.env["product.supplierinfo"].search_count([]), infos)

    def test_product_without_any_match_stays_pending(self):
        documents, _errors = self.Document.dfe_import_files(
            [("nfe.xml", self._depara_note(KEY_2, code=b"NO-MATCH-1"))]
        )

        line = documents.fiscal_line_ids
        self.assertEqual(line.import_state, "pending")

    def test_resolving_by_hand_teaches_the_next_note_of_the_supplier(self):
        first, _errors = self.Document.dfe_import_files(
            [("one.xml", self._depara_note(KEY_2, code=b"NO-MATCH-2"))]
        )
        product = self.env["product.product"].create({"name": "Chosen by hand"})
        line = first.fiscal_line_ids
        line.product_id = product
        line._apply_import_depara(product=product, uom=self.uom_unit)
        domain = [("product_code", "=", "NO-MATCH-2"), ("product_id", "=", product.id)]
        self.assertEqual(self.env["product.supplierinfo"].search_count(domain), 1)

        second, _errors = self.Document.dfe_import_files(
            [("two.xml", self._depara_note(KEY_3, code=b"NO-MATCH-2"))]
        )

        self.assertEqual(second.fiscal_line_ids.product_id, product)
        self.assertEqual(second.fiscal_line_ids.import_state, "resolved")
        self.assertEqual(self.env["product.supplierinfo"].search_count(domain), 1)

    def test_learned_factor_only_holds_for_the_same_declared_unit(self):
        kilo = self.env["uom.uom"]._match_by_fiscal_code("KG")
        product = self._supplier_product(
            uom=kilo, partner_uom_id=kilo.id, partner_uom_factor=2
        )

        same, _errors = self.Document.dfe_import_files(
            [("kg.xml", self._depara_note(KEY_2, unit=b"KG"))]
        )
        other, _errors = self.Document.dfe_import_files(
            [("un.xml", self._depara_note(KEY_3, unit=b"UN"))]
        )

        self.assertEqual(same.fiscal_line_ids.product_id, product)
        self.assertEqual(same.fiscal_line_ids.import_state, "resolved")
        self.assertEqual(same.fiscal_line_ids.quantity, 2)
        self.assertEqual(other.fiscal_line_ids.import_state, "matched")
        self.assertEqual(other.fiscal_line_ids.quantity, 2)

    def test_product_mapped_for_another_supplier_is_not_resolved(self):
        other = self.env["res.partner"].create({"name": "Another supplier"})
        product = self._supplier_product()
        product.seller_ids.write({"partner_id": other.id})

        documents, _errors = self.Document.dfe_import_files(
            [("nfe.xml", self._depara_note(KEY_2))]
        )

        self.assertEqual(documents.fiscal_line_ids.import_state, "pending")

    def test_resolving_by_hand_records_the_declared_unit_and_factor(self):
        kilo = self.env["uom.uom"]._match_by_fiscal_code("KG")
        first, _errors = self.Document.dfe_import_files(
            [("one.xml", self._depara_note(KEY_2, unit=b"KG", code=b"NO-MATCH-3"))]
        )
        product = self.env["product.product"].create({"name": "Chosen by hand"})
        line = first.fiscal_line_ids
        line.product_id = product
        line.import_uom_factor = 2

        line._apply_import_depara(product=product, uom=self.uom_unit)

        info = self.env["product.supplierinfo"].search(
            [("product_code", "=", "NO-MATCH-3")]
        )
        self.assertEqual((info.partner_uom_id, info.partner_uom_factor), (kilo, 2))
