import base64
import io
import os
import re
import zipfile
from unittest.mock import MagicMock, patch

import nfelib
import pkg_resources
from xsdata.formats.dataclass.parsers import XmlParser

from odoo import Command, fields
from odoo.tests import TransactionCase

from odoo.addons import l10n_br_nfe

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

    def _prepare_wizard(self, xml):
        self.wizard = self.env["l10n_br_fiscal.document.import.wizard"].create(
            {
                "company_id": self.env.ref("base.main_company").id,
                "file": base64.b64encode(xml),
            }
        )
        self.wizard._onchange_file()

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
        self._prepare_wizard(self.xml_1)
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
        product, and the import writes the canonical (PO name, line position)
        key onto the fiscal line — synthesizing the xPed/nItemPed the
        supplier XML didn't send, for the later bill matching."""
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
        self.assertEqual(fiscal_line.partner_order, order.name)
        self.assertEqual(fiscal_line.partner_order_line, "1")

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
