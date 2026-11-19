import base64
import importlib.resources
import io
import os
import re
import zipfile
from unittest.mock import MagicMock, patch

import nfelib
import pkg_resources
from psycopg2 import IntegrityError
from xsdata.formats.dataclass.parsers import XmlParser

from odoo import Command, fields, tools
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase
from odoo.tools import mute_logger

from odoo.addons import l10n_br_nfe
from odoo.addons.l10n_br_fiscal.constants.fiscal import FISCAL_TAX_ID_FIELDS

from ..wizards.document_import_wizard import DocumentImportWizard


class NFeImportWizardTest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        def test_xml_path(filename):
            return os.path.join(
                l10n_br_nfe.__path__[0],
                "tests",
                "nfe",
                "v4_00",
                "leiauteNFe",
                filename,
            )

        path_1 = test_xml_path("NFe35200181583054000129550010000000052062777166.xml")
        with open(path_1, "rb") as f:
            cls.xml_1 = f.read()

        cls.wizard = False
        cls.product_1 = cls.env["product.product"].create({"name": "Product Test 1"})
        cls.partner_1 = cls.env["res.partner"].create({"name": "Partner Test 1"})

    def _prepare_wizard(self, xml, company=None):
        if company is None:
            company = self.env.ref("base.main_company")
        self.wizard = self.env["l10n_br_fiscal.document.import.wizard"].create(
            {
                "company_id": company.id,
                "file": base64.b64encode(xml),
            }
        )
        self.wizard._onchange_file()
        return self.wizard

    def check_edoc(self, edoc):
        self.assertEqual(
            len(self.wizard.imported_products_ids),
            len(edoc.fiscal_line_ids),
        )
        self.assertTrue(edoc.partner_id)
        self.assertEqual(
            self.wizard.issuer_partner_id.vat,
            edoc.partner_id.vat,
        )
        self.assertEqual(
            self.wizard.issuer_partner_id.name,
            edoc.partner_id.name,
        )

    def test_import_nfe_xml(self):
        xml = "dummy"
        with self.assertRaises(ValueError):
            self._prepare_wizard(xml.encode("utf-8"))

        mock_document = MagicMock(spec=["modelo_documento"])
        mock_document.modelo_documento = "65"
        with (
            patch.object(
                DocumentImportWizard,
                "_extract_binding_data",
                return_value=mock_document,
            ),
            self.assertRaises(TypeError),
        ):
            self.wizard._check_xml_data(self.wizard._parse_file())

        self._prepare_wizard(self.xml_1)
        self.wizard._import_edoc()

        self.check_edoc(self.wizard.document_id)

        first_imported_product = self.wizard.imported_products_ids[0]

        self.assertEqual(
            self.wizard.document_key,
            "3520 0181 5830 5400 0129 5500 1000 0000 0520 6277 7166",
        )
        self.assertEqual(self.wizard.document_number, "5")
        self.assertEqual(self.wizard.document_serie, "1")
        self.assertEqual(self.wizard.issuer_partner_id.vat, "81.583.054/0001-29")
        self.assertEqual(self.wizard.issuer_partner_id.name, "Empresa Lucro Presumido")
        self.assertEqual(
            self.wizard.partner_id,
            self.env.ref("l10n_br_base.lucro_presumido_partner"),
        )
        self.assertEqual(
            f"[{first_imported_product.product_code}] "
            f"{first_imported_product.product_name}",
            "[E-COM11] Cabinet with Doors",
        )
        self.assertEqual(first_imported_product.uom_com, "UNID")
        self.assertEqual(first_imported_product.quantity_com, 1)
        self.assertEqual(first_imported_product.price_unit_com, 14)
        self.assertEqual(first_imported_product.uom_trib, "UNID")
        self.assertEqual(first_imported_product.quantity_trib, 1)
        self.assertEqual(first_imported_product.price_unit_trib, 14)
        self.assertEqual(first_imported_product.total, 14)

    def test_create_edoc_from_xml(self):
        self._prepare_wizard(self.xml_1)

        self.wizard.partner_id = False
        binding, edoc = self.wizard._create_edoc_from_file()
        self.assertEqual(self.wizard.partner_id, edoc.partner_id)

        self.check_edoc(edoc)

    def test_imported_document_view_xml_and_pdf(self):
        """Ver XML and Ver PDF must work on a document imported from a
        supplier XML, without an authorization event."""
        self._prepare_wizard(self.xml_1)
        binding, edoc = self.wizard._create_edoc_from_file()

        self.assertFalse(edoc.authorization_event_id)
        self.assertTrue(edoc.original_xml_file_id)
        self.assertEqual(
            base64.b64decode(edoc.original_xml_file_id.datas),
            self.xml_1,
        )
        state_edoc = edoc.state_edoc

        action = edoc.view_xml()
        self.assertIn(str(edoc.original_xml_file_id.id), action["url"])

        action = edoc.view_pdf()
        self.assertTrue(edoc.file_report_id)
        self.assertIn(str(edoc.file_report_id.id), action["url"])
        self.assertTrue(base64.b64decode(edoc.file_report_id.datas).startswith(b"%PDF"))

        self.assertFalse(edoc.authorization_event_id)
        self.assertEqual(edoc.state_edoc, state_edoc)

    def test_received_nfe_uses_the_company_operation_when_set(self):
        company = self.env.ref("l10n_br_base.empresa_simples_nacional")
        self.assertFalse(company.nfe_import_fiscal_operation_id)
        guessed = self._prepare_wizard(self.xml_1, company).fiscal_operation_id
        operation = self.env.ref("l10n_br_fiscal.fo_entrada_remessa")
        self.assertEqual(operation.fiscal_operation_type, "in")
        self.assertNotEqual(operation, guessed)
        company.nfe_import_fiscal_operation_id = operation
        wizard = self._prepare_wizard(self.xml_1, company)
        self.assertEqual(wizard.fiscal_operation_type, "in")
        self.assertEqual(wizard.fiscal_operation_id, operation)
        wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        _binding, edoc = wizard._create_edoc_from_file()
        self.assertEqual(
            edoc.fiscal_operation_id, self.env.ref("l10n_br_fiscal.fo_compras")
        )

    def test_an_outgoing_nfe_ignores_the_import_operation(self):
        company = self.env.ref("l10n_br_base.empresa_lucro_presumido")
        operation = self.env.ref("l10n_br_fiscal.fo_entrada_remessa")
        company.nfe_import_fiscal_operation_id = operation
        wizard = self._prepare_wizard(self.xml_1, company)
        self.assertEqual(wizard.fiscal_operation_type, "out")
        self.assertNotEqual(wizard.fiscal_operation_id, operation)

    def test_document_number_and_serie_keep_trailing_zeros(self):
        wizard = self.env["l10n_br_fiscal.document.import.wizard"].create({})
        wizard._extract_key_information("35261145990181000189550100000540901130178813")
        self.assertEqual(wizard.document_number, "54090")
        self.assertEqual(wizard.document_serie, "10")

    def FIXME_test_set_fiscal_operation_type(self):
        self._prepare_wizard(self.xml_1)

        doc = self.wizard._document_key_from_binding(self.wizard._parse_file())
        origin_company = self.wizard.company_id

        doc_company_id = self.env["res.company"].search(
            [("cnpj_cpf_stripped", "=", re.sub("[^0-9]", "", doc.cnpj_cpf_emitente))],
            limit=1,
        )
        self.wizard.company_id = doc_company_id
        self.wizard._set_fiscal_operation_type()
        self.assertEqual(self.wizard.fiscal_operation_type, "out")

        self.wizard.company_id = origin_company
        self.wizard._set_fiscal_operation_type()
        self.assertEqual(self.wizard.fiscal_operation_type, "in")

    def test_import_creates_reviewed_draft(self):
        """The import materializes a faithful document with per-line review
        states, the original XML attached and the supplier nomenclature
        preserved; the supplier info learning happens on the persisted
        line."""
        self._prepare_wizard(self.xml_1)
        self.wizard._import_edoc()
        document = self.wizard.document_id

        self.assertTrue(document.imported_document)
        self.assertTrue(document.import_state)
        self.assertTrue(all(line.import_state for line in document.fiscal_line_ids))
        attachment = self.env["ir.attachment"].search(
            [
                ("res_model", "=", "l10n_br_fiscal.document"),
                ("res_id", "=", document.id),
                ("name", "=ilike", "%.xml"),
            ]
        )
        self.assertTrue(attachment)

        line = document.fiscal_line_ids[0]
        # supplier nomenclature preserved on the line (spec fields)
        self.assertTrue(line.nfe40_cProd)
        self.assertEqual(line._get_partner_product_code(), line.nfe40_cProd)

        # The fiscal profile imports the XML without purchase access rights
        fiscal_user = self.env["res.users"].create(
            {
                "name": "Fiscal importer",
                "login": "fiscal_importer",
                "groups_id": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("l10n_br_fiscal.group_manager").id,
                            self.env.ref("l10n_br_nfe.group_manager").id,
                        ]
                    )
                ],
            }
        )

        # supplier info learning on the persisted line
        line.with_user(fiscal_user)._apply_import_depara()
        self.assertEqual(line.import_state, "resolved")
        self.assertTrue(line.import_supplierinfo_id)
        self.assertEqual(line.import_supplierinfo_id.product_code, line.nfe40_cProd)

    def test_import_binding_without_product_creation(self):
        """With create_missing_products=False an unmatched product line is
        left empty (pending review) instead of created as a side effect."""
        xml = self.xml_1.decode()
        xml = xml.replace("E-COM11", "NAOEXISTE1").replace(
            "Cabinet with Doors", "Produto Desconhecido XYZ"
        )
        binding = XmlParser().from_bytes(xml.encode())
        products_before = self.env["product.product"].search_count([])
        document = self.env["l10n_br_fiscal.document"].import_binding_nfe(
            binding, edoc_type="in", create_missing_products=False
        )
        self.assertEqual(self.env["product.product"].search_count([]), products_before)
        self.assertFalse(document.fiscal_line_ids[0].product_id)
        document._init_import_states()
        self.assertEqual(document.fiscal_line_ids[0].import_state, "pending")
        self.assertEqual(document.import_state, "pending")

    # ------------------------------------------------------------------
    # What the import resolves by itself, and what waits for a person
    # ------------------------------------------------------------------

    def _supplierinfo(self, partner, code="E-COM11"):
        return self.env["product.supplierinfo"].search(
            [("partner_id", "=", partner.id), ("product_code", "=", code)]
        )

    def _import_xml_1(self):
        self._prepare_wizard(self.xml_1)
        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        self.wizard._import_edoc()
        return self.wizard.document_id

    def test_a_product_guessed_by_the_import_is_only_suggested(self):
        """A product found by the internal reference, the barcode or the name
        is a guess: the line stays matched and the import teaches nothing to
        the supplier de-para until a person confirms it."""
        product = self._get_xml_product()
        issuer = self._create_xml_issuer_supplier()
        self._supplierinfo(issuer).unlink()
        document = self._import_xml_1()
        line = document.fiscal_line_ids[0]
        self.assertEqual(line.product_id, product)
        self.assertEqual(line.import_state, "matched")
        self.assertFalse(self._supplierinfo(document.partner_id))
        self.assertTrue(document.import_pending_count)
        # the confirmation is what resolves the line and teaches the de-para
        line.action_resolve_line()
        self.assertEqual(line.import_state, "resolved")
        self.assertTrue(self._supplierinfo(document.partner_id))

    def test_a_product_of_the_supplier_depara_is_resolved(self):
        """The de-para already learned for this same supplier needs no review."""
        product = self._get_xml_product()
        self._prepare_wizard(self.xml_1)
        issuer = self.wizard.issuer_partner_id
        self.env["product.supplierinfo"].create(
            {
                "partner_id": issuer.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_code": "E-COM11",
                "product_name": "Cabinet with Doors",
            }
        )
        self._prepare_wizard(self.xml_1)
        self.assertEqual(self.wizard.imported_products_ids.product_source, "supplier")
        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        self.wizard._import_edoc()
        line = self.wizard.document_id.fiscal_line_ids[0]
        self.assertEqual(line.product_id, product)
        self.assertEqual(line.import_state, "resolved")

    def test_the_de_para_of_another_supplier_is_not_trusted(self):
        """The same supplier code in the de-para of ANOTHER supplier is a
        coincidence: it is a guess here."""
        product = self._get_xml_product()
        self._prepare_wizard(self.xml_1)
        issuer = self.wizard.issuer_partner_id
        self._supplierinfo(issuer).unlink()
        other = self.env["res.partner"].create({"name": "Another supplier"})
        self.env["product.supplierinfo"].create(
            {
                "partner_id": other.id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_code": "E-COM11",
                "product_name": "Cabinet with Doors",
            }
        )
        document = self._import_xml_1()
        line = document.fiscal_line_ids[0]
        self.assertEqual(line.import_state, "matched")
        self.assertFalse(self._supplierinfo(document.partner_id))

    def test_the_product_chosen_in_the_grid_is_resolved_and_learned(self):
        """What the person chose in the grid is a human decision."""
        self._get_xml_product()
        chosen = self.env["product.product"].create(
            {"name": "Chosen in the grid", "purchase_ok": True}
        )
        self._prepare_wizard(self.xml_1)
        self._supplierinfo(self.wizard.issuer_partner_id).unlink()
        self.wizard.imported_products_ids.product_id = chosen
        self.assertEqual(self.wizard.imported_products_ids.product_source, "user")
        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        self.wizard._import_edoc()
        document = self.wizard.document_id
        line = document.fiscal_line_ids[0]
        self.assertEqual(line.product_id, chosen)
        self.assertEqual(line.import_state, "resolved")
        self.assertTrue(self._supplierinfo(document.partner_id))

    def test_confirming_the_suggestion_in_the_grid_counts_as_a_decision(self):
        product = self._get_xml_product()
        self._prepare_wizard(self.xml_1)
        self._supplierinfo(self.wizard.issuer_partner_id).unlink()
        self.wizard.imported_products_ids.product_confirmed = True
        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        self.wizard._import_edoc()
        document = self.wizard.document_id
        line = document.fiscal_line_ids[0]
        self.assertEqual(line.product_id, product)
        self.assertEqual(line.import_state, "resolved")
        self.assertTrue(self._supplierinfo(document.partner_id))

    def test_the_zip_never_resolves_a_guess(self):
        """Nobody sees the grid of a zip: what is guessed waits for review."""
        product = self._get_xml_product()
        issuer = self._create_xml_issuer_supplier()
        self._supplierinfo(issuer).unlink()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("nota1.xml", self.xml_1)
        wizard = self.env["l10n_br_fiscal.document.import.wizard"].create(
            {
                "company_id": self.env.ref("base.main_company").id,
                "file": base64.b64encode(buffer.getvalue()),
                "fiscal_operation_id": self.env.ref("l10n_br_fiscal.fo_compras").id,
            }
        )
        documents = wizard._import_edoc_batch()
        line = documents.fiscal_line_ids[0]
        self.assertEqual(line.product_id, product)
        self.assertEqual(line.import_state, "matched")
        self.assertFalse(self._supplierinfo(documents.partner_id))

    def _unknown_product_xml(self):
        return (
            self.xml_1.decode()
            .replace("E-COM11", "NAOEXISTE2")
            .replace("Cabinet with Doors", "Produto Desconhecido ZZZ")
            .encode()
        )

    def test_the_box_unchecked_creates_no_product(self):
        """The wizard creates no product unless the box asks for it: the line
        of an unmapped product waits, pending, for a person."""
        self.assertFalse(
            self.env["l10n_br_fiscal.document.import.wizard"]
            .create({})
            .allow_product_creation
        )
        products_before = self.env["product.product"].search_count([])
        self._prepare_wizard(self._unknown_product_xml())
        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        self.wizard._import_edoc()
        self.assertEqual(self.env["product.product"].search_count([]), products_before)
        line = self.wizard.document_id.fiscal_line_ids
        self.assertFalse(line.product_id)
        self.assertEqual(line.import_state, "pending")

    def test_the_box_checked_creates_the_product(self):
        products_before = self.env["product.product"].search_count([])
        self._prepare_wizard(self._unknown_product_xml())
        self.wizard.allow_product_creation = True
        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        self.wizard._import_edoc()
        self.assertEqual(
            self.env["product.product"].search_count([]), products_before + 1
        )
        line = self.wizard.document_id.fiscal_line_ids
        self.assertEqual(line.product_id.default_code, "NAOEXISTE2")

    def test_the_zip_follows_the_box_too(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("nota1.xml", self._unknown_product_xml())
        products_before = self.env["product.product"].search_count([])
        wizard = self.env["l10n_br_fiscal.document.import.wizard"].create(
            {
                "company_id": self.env.ref("base.main_company").id,
                "file": base64.b64encode(buffer.getvalue()),
            }
        )
        documents = wizard._import_edoc_batch()
        self.assertEqual(self.env["product.product"].search_count([]), products_before)
        self.assertFalse(documents.fiscal_line_ids.product_id)
        wizard.allow_product_creation = True
        # the box of the wizard goes to each entry of the archive
        entry = wizard.copy({"file": wizard.file})
        self.assertTrue(entry.allow_product_creation)

    # ------------------------------------------------------------------
    # The same note in two companies of the database, and the unique key
    # ------------------------------------------------------------------

    def _plain_document(self, number, key=False):
        issuer_company = self.env.ref("l10n_br_base.empresa_lucro_presumido")
        document = self.env["l10n_br_fiscal.document"].create(
            {
                "company_id": issuer_company.id,
                "document_type_id": self.env.ref("l10n_br_fiscal.document_55").id,
                "issuer": "company",
                "fiscal_operation_type": "out",
                "document_serie": "1",
                "document_number": number,
                "document_key": key,
            }
        )
        # the tests below read and write the table with SQL
        self.env.flush_all()
        return document

    def _outgoing_document_of_xml_1(self):
        """The document the issuer (a company of this database) has for the
        note of xml_1: the outgoing one."""
        return self._plain_document("5", "35200181583054000129550010000000052062777166")

    def test_the_import_does_not_find_the_outgoing_document_of_the_issuer(self):
        """The same note is the outgoing document of the issuer and the
        incoming one of the recipient. Importing it in the recipient must not
        return the outgoing document of the other company."""
        outgoing = self._outgoing_document_of_xml_1()
        self._prepare_wizard(self.xml_1)
        self.assertNotEqual(self.wizard.document_id, outgoing)
        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        _binding, document = self.wizard._import_edoc()
        self.assertNotEqual(document, outgoing)
        self.assertEqual(document.issuer, "partner")
        self.assertEqual(document.document_key, outgoing.document_key)

    def test_the_import_finds_the_document_of_its_own_company(self):
        """Importing again the file in the company that already imported it
        gives the same document: the search keeps finding what is its own."""
        outgoing = self._outgoing_document_of_xml_1()
        self._prepare_wizard(self.xml_1)
        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        _binding, first = self.wizard._import_edoc()
        self._prepare_wizard(self.xml_1)
        self.assertEqual(self.wizard.document_id, first)
        self.assertNotEqual(self.wizard.document_id, outgoing)

    def test_the_key_is_unique_in_the_database(self):
        """The uniqueness of the key is also guaranteed by the database: a
        second document with the same company, issuer and key is refused even
        when the check of the model is not reached (two imports at once)."""
        first = self._outgoing_document_of_xml_1()
        other = self._plain_document("6")
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            with self.env.cr.savepoint():
                self.env.cr.execute(
                    "UPDATE l10n_br_fiscal_document SET document_key = %s "
                    "WHERE id = %s",
                    [first.document_key, other.id],
                )
        # the cancelled documents do not hold the key
        self.env.cr.execute(
            "UPDATE l10n_br_fiscal_document SET state_edoc = 'cancelada' WHERE id = %s",
            [first.id],
        )
        self.env.cr.execute(
            "UPDATE l10n_br_fiscal_document SET document_key = %s WHERE id = %s",
            [first.document_key, other.id],
        )

    def test_the_check_of_the_key_goes_on_after_a_document_without_key(self):
        """A document without key must not stop the check of the others."""
        first = self._outgoing_document_of_xml_1()
        # the index is not what is being tested here
        self.env.cr.execute(
            "DROP INDEX IF EXISTS l10n_br_fiscal_document_unique_key_idx"
        )
        no_key = self._plain_document("6")
        duplicate = self._plain_document("7")
        self.env.cr.execute(
            "UPDATE l10n_br_fiscal_document SET document_key = %s WHERE id = %s",
            [first.document_key, duplicate.id],
        )
        duplicate.invalidate_recordset()
        with self.assertRaises(ValidationError):
            (no_key | duplicate)._check_key()

    def test_the_index_is_not_created_where_there_are_duplicated_keys(self):
        """A database that already has duplicated keys keeps working: the index
        is skipped with a warning, and nothing is deleted."""
        first = self._outgoing_document_of_xml_1()
        self.env.cr.execute(
            "DROP INDEX IF EXISTS l10n_br_fiscal_document_unique_key_idx"
        )
        duplicate = self._plain_document("6")
        self.env.cr.execute(
            "UPDATE l10n_br_fiscal_document SET document_key = %s WHERE id = %s",
            [first.document_key, duplicate.id],
        )
        with self.assertLogs(
            "odoo.addons.l10n_br_fiscal.models.document", level="WARNING"
        ) as logs:
            self.env["l10n_br_fiscal.document"].init()
        self.assertIn("duplicated keys", logs.output[0])
        self.assertIn(first.document_key, logs.output[0])
        self.assertFalse(
            tools.index_exists(self.env.cr, "l10n_br_fiscal_document_unique_key_idx")
        )
        self.assertTrue((first | duplicate).exists())

    def test_zip_batch_import(self):
        """A zip archive with several XMLs lands as several persisted
        documents waiting for review."""
        res_items = (
            "nfe",
            "samples",
            "v4_0",
            "leiauteNFe",
            "35180834128745000152550010000474281920007498-nfe.xml",
        )
        other_xml = pkg_resources.resource_stream(
            nfelib.__name__, "/".join(res_items)
        ).read()

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("nota1.xml", self.xml_1)
            archive.writestr("nota2.xml", other_xml)
            archive.writestr("leiame.txt", b"nao sou um xml")

        wizard = self.env["l10n_br_fiscal.document.import.wizard"].create(
            {
                "company_id": self.env.ref("base.main_company").id,
                "file": base64.b64encode(buffer.getvalue()),
            }
        )
        self.assertTrue(wizard._file_is_zip())
        documents = wizard._import_edoc_batch()
        self.assertEqual(len(documents), 2)
        self.assertTrue(all(documents.mapped("imported_document")))

    def test_match_xml_product(self):
        self._prepare_wizard(self.xml_1)

        xml = self.wizard._parse_file()
        xml_product_1 = xml.infNFe.det[0].prod
        prod_id = self.wizard._match_product(xml_product_1)
        self.assertEqual(prod_id, self.env.ref("product.product_product_10"))

        prod_code = self.env["product.product"].create(
            {
                "name": "TEST1",
                "default_code": "TEST123",
            }
        )

        mock_code = MagicMock(spec=["cProd"])
        mock_code.cProd = "TEST123"
        prod_id = self.wizard._match_product(mock_code)

        mock_code = MagicMock(spec=["cProd"])
        mock_code.cProd = "TEST123"
        prod_id = self.wizard._match_product(mock_code)
        self.assertEqual(prod_id, prod_code)

        prod_code.unlink()
        prod_barcode = self.env["product.product"].create(
            {"name": "TEST2", "barcode": "123456789123"}
        )
        mock_barcode = MagicMock(spec=["cEANTrib"])
        mock_barcode.cProd = False
        mock_barcode.cEANTrib = "123456789123"
        prod_id = self.wizard._match_product(mock_barcode)
        self.assertEqual(prod_id, prod_barcode)

        prod_barcode.unlink()
        prod_id = self.wizard._match_product(MagicMock())
        self.assertFalse(prod_id)

    def test_match_product_by_purchase(self):
        """xPed/nItemPed map to the buyer's purchase order reference and the
        1-based line POSITION (``sequence`` defaults to 10 for every
        interface-created line and cannot be used). When purchase is absent it
        must no-op so _match_product falls back to
        supplierinfo/default_code/barcode."""
        self._prepare_wizard(self.xml_1)
        pol_model = self.env.get("purchase.order.line")

        mock = MagicMock()
        mock.xPed = "NONEXISTENT-PO-REF"
        mock.nItemPed = "999"
        # No PO references this xPed (and/or purchase absent) -> no match,
        # and crucially no crash on a missing model.
        self.assertFalse(self.wizard._match_product_by_purchase(mock))

        if pol_model is None:
            # guard short-circuits before any purchase.order.line search
            self.assertFalse(
                self.wizard._match_product_by_purchase(
                    self.wizard._parse_file().infNFe.det[0].prod
                )
            )
            return

        company = self.env.ref("base.main_company")
        partner = self.env["res.partner"].create({"name": "Vendor PO"})
        first_product = self.env["product.product"].create({"name": "PO Product 1"})
        second_product = self.env["product.product"].create({"name": "PO Product 2"})
        order = self.env["purchase.order"].create(
            {"partner_id": partner.id, "company_id": company.id}
        )
        for product in (first_product, second_product):
            self.env["purchase.order.line"].create(
                {
                    "order_id": order.id,
                    "product_id": product.id,
                    "name": product.name,
                    "product_qty": 1.0,
                    "price_unit": 10.0,
                    "date_planned": fields.Datetime.now(),
                }
            )
        self.wizard.issuer_partner_id = partner
        self.wizard.company_id = company

        # nItemPed is the 1-based line position, not the (10, 10, ...) sequence.
        mock = MagicMock()
        mock.xPed = order.name
        mock.nItemPed = "1"
        self.assertEqual(self.wizard._match_product_by_purchase(mock), first_product)
        mock.nItemPed = "2"
        self.assertEqual(self.wizard._match_product_by_purchase(mock), second_product)

        # the buyer's vendor reference (partner_ref) also matches xPed.
        order.partner_ref = "SUPPLIER-PO-REF"
        mock = MagicMock()
        mock.xPed = "SUPPLIER-PO-REF"
        mock.nItemPed = "2"
        self.assertEqual(self.wizard._match_product_by_purchase(mock), second_product)

        # an out-of-range nItemPed falls back to the cProd disambiguation.
        second_product.default_code = "COD-2"
        mock = MagicMock()
        mock.xPed = order.name
        mock.nItemPed = "99"
        mock.cProd = "COD-2"
        mock.cEANTrib = None
        self.assertEqual(self.wizard._match_product_by_purchase(mock), second_product)

        # a purchase order in another company must not match (multi-company).
        other_company = self.env["res.company"].create(
            {"name": "Other Co", "currency_id": company.currency_id.id}
        )
        foreign_order = self.env["purchase.order"].create(
            {"partner_id": partner.id, "company_id": other_company.id}
        )
        self.env["purchase.order.line"].create(
            {
                "order_id": foreign_order.id,
                "product_id": first_product.id,
                "name": first_product.name,
                "product_qty": 1.0,
                "price_unit": 10.0,
                "date_planned": fields.Datetime.now(),
            }
        )
        foreign_order.partner_ref = "FOREIGN-COMPANY-REF"
        mock = MagicMock()
        mock.xPed = "FOREIGN-COMPANY-REF"
        mock.nItemPed = "1"
        self.assertFalse(self.wizard._match_product_by_purchase(mock))

    def test_import_nfe_created_product_uom_from_xml(self):
        """A product created during import gets its unit from the XML uCom.

        The fiscal line's uom is computed from the product, but for a product
        created during the import that computation runs before the product's
        units are resolved, so the wizard must fall back to the unit it
        matched from the XML uCom/uTrib. Otherwise ``_check_document_import``
        rejects the document with "no unit of measure".
        """
        # a product the base does not have, so that the import really creates it
        self._prepare_wizard(self._unknown_product_xml())
        self.wizard.allow_product_creation = True
        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        _binding, edoc = self.wizard._import_edoc()
        if hasattr(edoc, "_check_document_import"):
            # integrity guard lives in l10n_br_account, which l10n_br_nfe
            # does not depend on: skip it when the module is not installed
            edoc._check_document_import()  # must not raise
        self.assertTrue(edoc.fiscal_line_ids)
        for line in edoc.fiscal_line_ids:
            self.assertTrue(
                line.uom_id, "created-product line must get a uom from the XML"
            )
            self.assertTrue(
                line.product_id.uom_id,
                "product created during import must get the XML unit",
            )

    def test_created_product_takes_the_xml_unit_and_is_stockable(self):
        kg = self.env.ref("uom.product_uom_kgm")
        kg.code = "KG"
        xml = self.xml_1.replace(b"<uCom>UNID</uCom>", b"<uCom>KG</uCom>")
        xml = re.sub(rb"<(cProd|xProd)>", rb"<\1>NEWKG-", xml)
        xml = re.sub(rb"<cEAN(Trib)?>[^<]*</", rb"<cEAN\1>SEM GTIN</", xml)
        self._prepare_wizard(xml)
        self.wizard.allow_product_creation = True
        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        _binding, edoc = self.wizard._import_edoc()
        for line in edoc.fiscal_line_ids:
            product = line.product_id
            self.assertEqual(product.uom_id, kg)
            self.assertEqual(product.uom_po_id, product.uom_id)
            if "stock.move" in self.env:
                self.assertEqual(product.type, "product")

    def test_unmapped_unit_leaves_the_line_pending(self):
        xml = self.xml_1.replace(b"<uCom>UNID</uCom>", b"<uCom>ZZZ</uCom>")
        # a product no one has ever registered, so it would have to be created
        xml = re.sub(rb"<(cProd|xProd)>", rb"<\1>NEW-", xml)
        xml = re.sub(rb"<cEAN(Trib)?>[^<]*</", rb"<cEAN\1>SEM GTIN</", xml)
        self._prepare_wizard(xml)
        self.wizard.allow_product_creation = True
        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        _binding, edoc = self.wizard._import_edoc()
        self.assertFalse(edoc.fiscal_line_ids.mapped("product_id"))

    def test_imported_line_shows_all_its_taxes_in_the_fiscal_taxes_column(self):
        self._prepare_wizard(self.xml_1)
        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        _binding, edoc = self.wizard._import_edoc()
        for line in edoc.fiscal_line_ids:
            own = self.env["l10n_br_fiscal.tax"]
            for field in FISCAL_TAX_ID_FIELDS:
                own |= line[field]
            self.assertTrue(line.icms_tax_id)
            self.assertEqual(line.fiscal_tax_ids, own)

    def test_importing_the_same_file_twice_gives_the_same_document(self):
        self._prepare_wizard(self.xml_1)
        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        _binding, first = self.wizard._import_edoc()
        self._prepare_wizard(self.xml_1)
        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        _binding, second = self.wizard._import_edoc()
        self.assertEqual(first, second)
        self.assertEqual(
            self.env["l10n_br_fiscal.document"].search_count(
                [("document_key", "=", first.document_key)]
            ),
            1,
        )

    def test_the_operation_follows_the_cfop_declared_by_the_issuer(self):
        wizard = self.env["l10n_br_fiscal.document.import.wizard"].create({})
        purchase = self.env.ref("l10n_br_fiscal.fo_compras")
        for cfop in ("5101", "5102", "6101", "6102"):
            self.assertEqual(
                wizard._find_fiscal_operation(cfop, "VENDA", "in"), purchase
            )

    def test_the_create_policy_decides_what_an_unmapped_product_does(self):
        product = self.env["product.product"]
        rec_dict = {}
        parent_dict = {
            "nfe40_xProd": "Policy product",
            "nfe40_cProd": "POLICY-1",
            "nfe40_uCom": "ZZZ",
        }
        # an unmapped unit leaves the product unset...
        self.assertFalse(product.match_or_create_m2o(rec_dict, parent_dict))
        # ...or stops the import when the caller asks for a strict policy
        strict = product.with_context(spec_create_forbidden_action="raise")
        with self.assertRaises(UserError):
            strict.match_or_create_m2o(rec_dict, parent_dict)
        # a product forbidden by the caller is not created even with a unit
        parent_dict["nfe40_uCom"] = "UNID"
        forbidden = product.with_context(
            spec_create_forbidden_models=["product.product"]
        )
        self.assertFalse(forbidden.match_or_create_m2o({}, parent_dict))

    def _authorized_nfe_xml(self):
        return (
            importlib.resources.files(nfelib.__name__)
            .joinpath(
                "nfe",
                "samples",
                "v4_0",
                "leiauteNFe",
                "35180834128745000152550010000474281920007498-nfe.xml",
            )
            .read_bytes()
        )

    def test_a_cancelled_or_denied_nfe_is_not_imported(self):
        xml = self._authorized_nfe_xml()
        self.assertIn(b"<cStat>100</cStat>", xml)
        self._prepare_wizard(xml)
        self.assertFalse(self.wizard._import_block_reason())
        for status in (b"101", b"110"):
            blocked = xml.replace(
                b"<cStat>100</cStat>", b"<cStat>" + status + b"</cStat>"
            )
            self._prepare_wizard(blocked)
            self.assertTrue(self.wizard._import_block_reason())
            with self.assertRaises(UserError):
                self.wizard._import_edoc()
        self.assertFalse(
            self.env["l10n_br_fiscal.document"].search(
                [("document_key", "=", "35180834128745000152550010000474281920007498")]
            )
        )

    def test__parse_xml(self):
        self._prepare_wizard(self.xml_1)

        first_product = self.wizard.imported_products_ids[0]
        first_product.new_cfop_id = self.env.ref("l10n_br_fiscal.cfop_5111").id

        # The parsed binding is NEVER rewritten anymore: the file keeps the
        # supplier data (audit trail) and the CFOP override is applied on
        # the persisted document line instead.
        xml = self.wizard._parse_file()
        first_xml_product = xml.infNFe.det[0].prod
        self.assertEqual(first_xml_product.CFOP, "5102")

        self.wizard._import_edoc()
        self.assertEqual(
            self.wizard.document_id.fiscal_line_ids[0].cfop_id.code, "5111"
        )

        mock_prod = MagicMock(spec=["imposto"])
        mock_prod.imposto.ICMS.ICMS60.pICMS = 60
        mock_prod.imposto.ICMS.ICMS60.vICMS = 100
        mock_prod.imposto.IPI.IPITrib.pIPI = 5
        mock_prod.imposto.IPI.IPITrib.vIPI = 100
        taxes = self.wizard._get_taxes_from_xml_product(mock_prod)

        self.assertEqual(taxes["pICMS"], 60)
        self.assertEqual(taxes["vICMS"], 100)
        self.assertEqual(taxes["pIPI"], 5)
        self.assertEqual(taxes["vIPI"], 100)
        self.assertEqual(self.wizard.amount_total, 14.00)

    def test_cfop_warning(self):
        """The wizard line flags a CFOP whose scope (intra/interstate) is
        inconsistent with the real issuer/company geography."""
        sp = self.env.ref("base.state_br_sp")
        rj = self.env.ref("base.state_br_rj")
        company = self.env.ref("base.main_company")
        company.state_id = sp
        issuer = self.env["res.partner"].create(
            {"name": "Issuer SP", "state_id": sp.id}
        )
        wizard = self.env["l10n_br_fiscal.document.import.wizard"].create(
            {"company_id": company.id, "issuer_partner_id": issuer.id}
        )
        line = self.env["l10n_br_fiscal.document.import.wizard.line"].create(
            {"import_xml_id": wizard.id}
        )

        # interstate CFOP but both parties in SP -> warn
        line.cfop_xml = "6101"
        self.assertTrue(line.cfop_warning)

        # intrastate CFOP and both parties in SP -> no warning
        line.cfop_xml = "1101"
        self.assertFalse(line.cfop_warning)

        # issuer now in RJ: intrastate CFOP is inconsistent -> warn
        issuer.state_id = rj
        line._compute_cfop_warning()
        self.assertTrue(line.cfop_warning)

        # interstate CFOP with issuer RJ / company SP -> consistent, no warning
        line.cfop_xml = "6101"
        line._compute_cfop_warning()
        self.assertFalse(line.cfop_warning)

    # ------------------------------------------------------------------
    # Match source candidates (open PO lines / pending incoming moves)
    # ------------------------------------------------------------------

    def _create_xml_issuer_supplier(self):
        """Partner matching the xml_1 issuer CNPJ so the wizard links it
        during _onchange_file (preselection happens at parse time). Reused
        when demo data already carries that CNPJ."""
        supplier = self.env["res.partner"].search(
            [("cnpj_cpf_stripped", "=", "81583054000129")], limit=1
        )
        if not supplier:
            supplier = self.env["res.partner"].create(
                {"name": "XML Issuer Supplier", "cnpj_cpf": "81.583.054/0001-29"}
            )
        return supplier

    def _get_xml_product(self, **vals):
        """Product matching the xml_1 first-line product (code E-COM11).
        Reused when it already exists — some environments (e.g. jung's
        product module) enforce unique default_code."""
        product = self.env["product.product"].search(
            [("default_code", "=", "E-COM11")], limit=1
        )
        if not product:
            product = self.env["product.product"].create(
                dict(
                    {
                        "name": "Cabinet with Doors",
                        "default_code": "E-COM11",
                        "purchase_ok": True,
                    },
                    **vals,
                )
            )
        return product

    def _create_confirmed_po(self, partner, products):
        company = self.env.ref("base.main_company")
        order = self.env["purchase.order"].create(
            {"partner_id": partner.id, "company_id": company.id}
        )
        if (
            "fiscal_operation_id" in order._fields
            and company.purchase_fiscal_operation_id
        ):
            # l10n_br_purchase installed: the fiscal operation is required to
            # confirm the order
            order.fiscal_operation_id = company.purchase_fiscal_operation_id
        for product in products:
            self.env["purchase.order.line"].create(
                {
                    "order_id": order.id,
                    "product_id": product.id,
                    "name": product.name,
                    "product_qty": 2.0,
                    "price_unit": 10.0,
                    "date_planned": fields.Datetime.now(),
                }
            )
        order.with_context(tracking_disable=True).button_confirm()
        return order

    def test_match_source_preselection_and_writeback(self):
        """A single open PO line for the XML product is preselected as the
        match source (even when its receipt move exists too), sets the
        product, and the import writes it as the origin of the fiscal line, which
        is what the later bill matching follows (the xPed/nItemPed the supplier
        did not send stay empty)."""
        if self.env.get("purchase.order") is None:
            self.skipTest("purchase module not installed")
        supplier = self._create_xml_issuer_supplier()
        product = self._get_xml_product()
        order = self._create_confirmed_po(supplier, [product])

        self._prepare_wizard(self.xml_1)
        self.assertTrue(self.wizard.match_source_available)
        line = self.wizard.imported_products_ids[0]
        self.assertTrue(line.match_source_id)
        source = line.match_source_id
        # with purchase_stock the receipt move wins over its own PO line
        if (
            "purchase_line_id"
            in self.env.get("stock.move", self.env["purchase.order.line"])._fields
        ):
            self.assertEqual(source.source_type, "stock_move")
            self.assertEqual(source.po_ref, order.name)
            self.assertEqual(source.po_line_no, 1)
        else:
            self.assertEqual(source.source_type, "po_line")
            self.assertEqual(source.id, order.order_line.id)
        self.assertEqual(line.product_id, product)
        self.assertEqual(line.uom_internal, product.uom_id)

        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        _binding, edoc = self.wizard._import_edoc()
        fiscal_line = edoc.fiscal_line_ids[0]
        # the origin is the one chosen on the import; the (partner_order,
        # partner_order_line) pair is what the supplier declared, and the file
        # declared nothing
        self.assertEqual(fiscal_line.import_purchase_line_id, order.order_line)
        self.assertFalse(fiscal_line.partner_order)
        self.assertFalse(fiscal_line.partner_order_line)

    def test_match_source_ambiguity_no_preselection(self):
        """The same product on two lines of the same PO (or on two POs)
        leaves the match source empty: only the operator can tell which line
        the NFe line is for."""
        if self.env.get("purchase.order") is None:
            self.skipTest("purchase module not installed")
        supplier = self._create_xml_issuer_supplier()
        product = self._get_xml_product()
        order = self._create_confirmed_po(supplier, [product, product])

        self._prepare_wizard(self.xml_1)
        line = self.wizard.imported_products_ids[0]
        self.assertFalse(line.match_source_id)
        self.assertEqual(line.product_id, product)  # product still matched

        # the dropdown finds the two lines, disambiguated by position
        candidates = self.env[
            "l10n_br_fiscal.document.import.match.candidate"
        ].name_search(order.name)
        labels = [label for _id, label in candidates]
        self.assertTrue(any("#1" in label for label in labels))
        self.assertTrue(any("#2" in label for label in labels))

    def test_match_source_xped_preselection(self):
        """xPed/nItemPed pin the exact PO line even when the product appears
        on several lines/orders."""
        if self.env.get("purchase.order") is None:
            self.skipTest("purchase module not installed")
        supplier = self._create_xml_issuer_supplier()
        product = self._get_xml_product()
        order = self._create_confirmed_po(supplier, [product, product])

        self._prepare_wizard(self.xml_1)
        mock = MagicMock()
        mock.xPed = order.name
        mock.nItemPed = "2"
        candidate = self.wizard._match_import_candidate(mock, product)
        self.assertTrue(candidate)
        self.assertEqual(candidate.source_type, "po_line")
        self.assertEqual(candidate.id, order.order_line[1].id)

    def test_match_source_stock_move_candidate(self):
        """A standalone incoming picking (no PO, e.g. simples remessa) shows
        up as a match source candidate with a negative (stock.move) id."""
        if self.env.get("stock.picking") is None:
            self.skipTest("stock module not installed")
        supplier = self._create_xml_issuer_supplier()
        company = self.env.ref("base.main_company")
        product = self._get_xml_product(type="product")
        picking_type = self.env["stock.picking.type"].search(
            [("code", "=", "incoming"), ("company_id", "=", company.id)], limit=1
        )
        dest_location = picking_type.default_location_dest_id
        location_src = self.env.ref("stock.stock_location_suppliers")
        picking = self.env["stock.picking"].create(
            {
                "partner_id": supplier.id,
                "picking_type_id": picking_type.id,
                "location_id": location_src.id,
                "location_dest_id": dest_location.id,
                "move_ids": [
                    Command.create(
                        {
                            "name": product.name,
                            "product_id": product.id,
                            "product_uom_qty": 4.0,
                            "product_uom": product.uom_id.id,
                            "location_id": location_src.id,
                            "location_dest_id": dest_location.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()

        candidate = self.env["l10n_br_fiscal.document.import.match.candidate"].search(
            [
                ("source_type", "=", "stock_move"),
                ("partner_id", "=", supplier.id),
                ("product_id", "=", product.id),
            ]
        )
        self.assertEqual(len(candidate), 1)
        self.assertLess(candidate.id, 0)
        self.assertEqual(candidate.ref_name, picking.name)
        self.assertFalse(candidate.po_ref)
        label = candidate.name_get()[0][1]
        self.assertIn(picking.name, label)
        self.assertIn("E-COM11", label)

    def test_match_source_product_flag_and_star(self):
        """The line tells whether the issuer has candidates for its product
        (match_source_product_matched, drives the row decoration) and the
        dropdown flags those candidates with a leading '*', proposed first
        without restricting the search."""
        if self.env.get("purchase.order") is None:
            self.skipTest("purchase module not installed")
        supplier = self._create_xml_issuer_supplier()
        product = self._get_xml_product()
        order = self._create_confirmed_po(supplier, [product])

        self._prepare_wizard(self.xml_1)
        line = self.wizard.imported_products_ids[0]
        self.assertTrue(line.match_source_product_matched)

        # candidates of the line's product are starred and come first
        candidates = self.env["l10n_br_fiscal.document.import.match.candidate"]
        with_line_product = candidates.with_context(line_product_id=product.id)
        results = with_line_product.name_search(
            order.name,
            args=[
                ("partner_id", "=", supplier.id),
                ("company_id", "=", self.env.company.id),
            ],
        )
        self.assertTrue(results)
        self.assertTrue(results[0][1].startswith("* "))
        # without the context key no candidate is starred
        plain = candidates.name_search(
            order.name,
            args=[
                ("partner_id", "=", supplier.id),
                ("company_id", "=", self.env.company.id),
            ],
        )
        self.assertTrue(plain)
        self.assertFalse(any(label.startswith("* ") for _id, label in plain))

        # a product with no open candidate at all is flagged as such
        out_of_scope = self.env["product.product"].create(
            {"name": "No Candidate Product", "default_code": "NO-CANDIDATE"}
        )
        # the UI onchange clears the selected source when the product changes,
        # and the server-side constraint enforces the same coherence, so a raw
        # write must clear it too
        line.match_source_id = False
        line.product_id = out_of_scope
        line.invalidate_recordset(["match_source_product_matched"])
        line._compute_match_source_product_matched()
        self.assertFalse(line.match_source_product_matched)

    def test_match_source_empty_without_purchase_and_stock(self):
        """With neither purchase nor stock installed the candidate view is
        empty and the wizard behaves exactly as before (plain product
        picker, no match source)."""
        if (
            self.env.get("purchase.order") is not None
            or self.env.get("stock.move") is not None
        ):
            self.skipTest("purchase/stock installed: empty case not testable here")
        self._prepare_wizard(self.xml_1)
        self.assertFalse(self.wizard.match_source_available)
        self.assertFalse(self.wizard.imported_products_ids.match_source_id)

    # ------------------------------------------------------------------
    # OCA review follow-ups (duplicate XML lines, xPed ambiguity, open qty,
    # server-side validation of the selected source)
    # ------------------------------------------------------------------

    def _duplicate_first_det(self, xml):
        """Return the XML with its first <det> item duplicated.

        The bundled NFe fixtures all carry distinct products, so the
        "supplier split the same product over two invoice lines" scenario —
        the one demoed with the Jung NFes — needs its own fixture.
        """
        text = xml.decode("utf-8")
        match = re.search(r"<det\b.*?</det>", text, re.S)
        self.assertTrue(match, "no <det> item found in the test XML")
        duplicated = match.group(0).replace('nItem="1"', 'nItem="2"', 1)
        return (text[: match.end()] + duplicated + text[match.end() :]).encode("utf-8")

    def test_match_source_writeback_duplicate_product_lines(self):
        """The same product on two XML lines, with two DIFFERENT sources
        picked by the operator, must give each fiscal line its own origin.

        Regression: the write-back used to index the wizard lines by
        product (a dict), so the last line won and both fiscal lines were
        given the same origin — silently reconciling one of them against
        the wrong receipt.
        """
        if self.env.get("purchase.order") is None:
            self.skipTest("purchase module not installed")
        supplier = self._create_xml_issuer_supplier()
        product = self._get_xml_product()
        order = self._create_confirmed_po(supplier, [product, product])

        self._prepare_wizard(self._duplicate_first_det(self.xml_1))
        lines = self.wizard.imported_products_ids
        self.assertEqual(len(lines), 2)
        self.assertEqual(set(lines.mapped("product_id")), {product})
        # two identical PO lines for the product = ambiguous: the operator
        # chooses one source per XML line (here deliberately REVERSED, so a
        # "same source on both lines" bug cannot pass by accident)
        sources = self.env["l10n_br_fiscal.document.import.match.candidate"].search(
            [
                ("source_type", "=", "po_line"),
                ("partner_id", "=", supplier.id),
                ("product_id", "=", product.id),
            ],
            order="line_no",
        )
        self.assertEqual(len(sources), 2)
        lines[0].match_source_id = sources[1]
        lines[1].match_source_id = sources[0]

        self.wizard.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_compras")
        _binding, edoc = self.wizard._import_edoc()
        self.assertEqual(len(edoc.fiscal_line_ids), 2)
        self.assertEqual(
            edoc.fiscal_line_ids.mapped("import_purchase_line_id"),
            order.order_line[1] | order.order_line[0],
            "each fiscal line must carry the origin of ITS own source",
        )
        self.assertEqual(
            edoc.fiscal_line_ids[0].import_purchase_line_id, order.order_line[1]
        )
        self.assertEqual(
            edoc.fiscal_line_ids[1].import_purchase_line_id, order.order_line[0]
        )
        # what the supplier declared is not rewritten by the origin
        self.assertEqual(edoc.fiscal_line_ids.mapped("partner_order"), [False, False])

    def test_match_po_line_ambiguous_xped(self):
        """A duplicated xPed must not pick an order arbitrarily: disambiguate
        on the XML item, and leave the source empty when that is not enough."""
        if self.env.get("purchase.order") is None:
            self.skipTest("purchase module not installed")
        supplier = self._create_xml_issuer_supplier()
        product = self._get_xml_product()
        other = self.env["product.product"].create(
            {"name": "Other XML Product", "default_code": "OTHER-PROD"}
        )
        order_item = self._create_confirmed_po(supplier, [product])
        order_other = self._create_confirmed_po(supplier, [other])
        order_item.partner_ref = "XPED-AMB"
        order_other.partner_ref = "XPED-AMB"

        self._prepare_wizard(self.xml_1)
        mock = MagicMock()
        mock.xPed = "XPED-AMB"
        mock.nItemPed = ""
        mock.cProd = "E-COM11"
        mock.cEANTrib = ""
        # only one of the two orders carries the XML item: that one wins
        self.assertEqual(
            self.wizard._match_po_line(mock),
            order_item.order_line,
        )

        # both orders carry the item: ambiguous, the operator decides
        order_other.order_line.product_id = product
        self.assertFalse(self.wizard._match_po_line(mock))

    def test_match_source_candidate_requires_open_quantity(self):
        """A receipt line with nothing left to receive is not proposed as a
        match source (open quantity = product_uom_qty - quantity_done)."""
        if self.env.get("stock.picking") is None:
            self.skipTest("stock module not installed")
        supplier = self._create_xml_issuer_supplier()
        company = self.env.ref("base.main_company")
        product = self._get_xml_product(type="product")
        picking_type = self.env["stock.picking.type"].search(
            [("code", "=", "incoming"), ("company_id", "=", company.id)], limit=1
        )
        location_src = self.env.ref("stock.stock_location_suppliers")
        location_dest = picking_type.default_location_dest_id
        picking = self.env["stock.picking"].create(
            {
                "partner_id": supplier.id,
                "picking_type_id": picking_type.id,
                "location_id": location_src.id,
                "location_dest_id": location_dest.id,
                "move_ids": [
                    Command.create(
                        {
                            "name": product.name,
                            "product_id": product.id,
                            "product_uom_qty": 4.0,
                            "product_uom": product.uom_id.id,
                            "location_id": location_src.id,
                            "location_dest_id": location_dest.id,
                        }
                    )
                ],
            }
        )
        picking.action_confirm()
        picking.action_assign()
        candidates = self.env["l10n_br_fiscal.document.import.match.candidate"].search(
            [
                ("source_type", "=", "stock_move"),
                ("partner_id", "=", supplier.id),
                ("product_id", "=", product.id),
            ]
        )
        self.assertEqual(len(candidates), 1, "the open move is proposed")

        # the warehouse already prepared the full quantity: nothing left to
        # receive, so the move is no longer an open source
        picking.move_ids.quantity_done = 4.0
        self.env.flush_all()
        candidates = self.env["l10n_br_fiscal.document.import.match.candidate"].search(
            [
                ("source_type", "=", "stock_move"),
                ("partner_id", "=", supplier.id),
                ("product_id", "=", product.id),
            ]
        )
        self.assertFalse(candidates, "a fully prepared move must not be proposed")

    def test_match_source_constraint_on_write(self):
        """The match source is validated server-side: another supplier's or
        another product's source cannot be written on the line."""
        if self.env.get("purchase.order") is None:
            self.skipTest("purchase module not installed")
        supplier = self._create_xml_issuer_supplier()
        product = self._get_xml_product()
        self._create_confirmed_po(supplier, [product])

        self._prepare_wizard(self.xml_1)
        line = self.wizard.imported_products_ids[0]
        self.assertTrue(line.match_source_id, "the single candidate is preselected")

        # a candidate of ANOTHER supplier
        other_supplier = self.env["res.partner"].create({"name": "Other Supplier"})
        self._create_confirmed_po(other_supplier, [product])
        foreign = self.env["l10n_br_fiscal.document.import.match.candidate"].search(
            [("partner_id", "=", other_supplier.id)], limit=1
        )
        self.assertTrue(foreign)
        with self.assertRaises(ValidationError):
            line.match_source_id = foreign

        # a candidate of the same supplier but ANOTHER product
        other_product = self.env["product.product"].create(
            {"name": "Another Candidate Product", "default_code": "CAND-OTHER"}
        )
        self._create_confirmed_po(supplier, [other_product])
        wrong_product = self.env[
            "l10n_br_fiscal.document.import.match.candidate"
        ].search(
            [
                ("partner_id", "=", supplier.id),
                ("product_id", "=", other_product.id),
            ],
            limit=1,
        )
        self.assertTrue(wrong_product)
        with self.assertRaises(ValidationError):
            line.match_source_id = wrong_product
