# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.tests.common import tagged

from odoo.addons.l10n_br_account.tests.common import AccountMoveBRCommon


@tagged("post_install", "-at_install")
class TestImportFiscalDocumentPOLink(AccountMoveBRCommon):
    """Importing a supplier fiscal document into a vendor bill links the bill
    lines to the open purchase order lines of that vendor."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document_type_55 = cls.env.ref("l10n_br_fiscal.document_55")
        cls.fo_compras = cls.env.ref("l10n_br_fiscal.fo_compras")
        cls.fo_compras_line = cls.env.ref("l10n_br_fiscal.fo_compras_compras")
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.uom_kg = cls.env.ref("uom.product_uom_kgm")
        cls.number = 6000
        if "l10n_latam.document.type" in cls.env:
            cls._mirror_latam_document_type()

    @classmethod
    def _mirror_latam_document_type(cls):
        fiscal_country = cls.company_data["company"].account_fiscal_country_id
        domain = [
            ("code", "=", cls.document_type_55.code),
            ("country_id", "=", fiscal_country.id),
        ]
        if not cls.env["l10n_latam.document.type"].search_count(domain):
            cls.env["l10n_latam.document.type"].create(
                {
                    "name": cls.document_type_55.name,
                    "code": cls.document_type_55.code,
                    "country_id": fiscal_country.id,
                    "internal_type": "invoice",
                    "doc_code_prefix": "NFe",
                }
            )

    def _create_po(self, products_qty, partner_order=None, name_ref=None):
        """products_qty: list of (product, qty[, partner_order_line])."""
        lines = []
        for item in products_qty:
            product, qty = item[0], item[1]
            vals = {
                "product_id": product.id,
                "product_qty": qty,
                "price_unit": 38.0,
                "product_uom": product.uom_id.id,
                "name": product.name,
            }
            if partner_order:
                vals["partner_order"] = partner_order
            if len(item) > 2:
                vals["partner_order_line"] = item[2]
            lines.append((0, 0, vals))
        po = self.env["purchase.order"].create(
            {
                "partner_id": self.partner_a.id,
                "company_id": self.company_data["company"].id,
                "partner_ref": name_ref or False,
                "order_line": lines,
            }
        )
        po.button_confirm()
        # bill all ordered quantities, not only the received ones
        po.order_line.product_id.product_tmpl_id.purchase_method = "purchase"
        return po

    def _create_fiscal_document(self, lines):
        """lines: list of dict(product, qty, price, uom, xped, nitemped)."""
        self.number += 1
        document = self.env["l10n_br_fiscal.document"].create(
            {
                "fiscal_operation_id": self.fo_compras.id,
                "document_type_id": self.document_type_55.id,
                "document_serie": "1",
                "document_number": str(self.number),
                "document_date": fields.Date.from_string("2026-08-17"),
                "issuer": "partner",
                "partner_id": self.partner_a.id,
                "fiscal_operation_type": "in",
                "imported_document": True,
            }
        )
        for item in lines:
            self.env["l10n_br_fiscal.document.line"].create(
                {
                    "document_id": document.id,
                    "name": item["product"].name,
                    "product_id": item["product"].id,
                    "quantity": item["qty"],
                    "price_unit": item.get("price", 38.0),
                    "uot_id": item.get("uom", self.uom_unit).id,
                    "partner_order": item.get("xped", False),
                    "partner_order_line": item.get("nitemped", False),
                    "fiscal_operation_type": "in",
                    "fiscal_operation_id": self.fo_compras.id,
                    "fiscal_operation_line_id": self.fo_compras_line.id,
                }
            )
        return document

    def _import(self, document, move_id=None):
        result = (
            self.env["account.move"]
            .sudo()
            .import_fiscal_document(document, move_id=move_id, move_type="in_invoice")
        )
        return self.env["account.move"].sudo().browse(result.id)

    def test_link_by_xped_and_nitemped(self):
        po = self._create_po(
            [(self.product_a, 5, "1"), (self.product_a, 5, "2")],
            partner_order="PED77",
        )
        pol1, pol2 = po.order_line
        document = self._create_fiscal_document(
            [{"product": self.product_a, "qty": 5, "xped": "PED77", "nitemped": "2"}]
        )
        move = self._import(document)
        self.assertEqual(len(move.invoice_line_ids), 1)
        self.assertEqual(move.invoice_line_ids.purchase_line_id, pol2)
        self.assertEqual(pol2.qty_invoiced, 5)
        self.assertEqual(pol1.qty_invoiced, 0)
        self.assertIn(po.name, move.invoice_origin)
        self.assertEqual(po.invoice_ids, move)
        self.assertEqual(move.fiscal_document_id, document)

    def test_link_by_xped_matching_po_name(self):
        po = self._create_po([(self.product_a, 5)])
        document = self._create_fiscal_document(
            [{"product": self.product_a, "qty": 5, "xped": po.name}]
        )
        move = self._import(document)
        self.assertEqual(move.invoice_line_ids.purchase_line_id, po.order_line)

    def test_link_by_product_oldest_po_first(self):
        po_old = self._create_po([(self.product_a, 5)])
        po_new = self._create_po([(self.product_a, 5)])
        po_new.date_order = fields.Datetime.add(po_old.date_order, days=3)
        document = self._create_fiscal_document([{"product": self.product_a, "qty": 5}])
        move = self._import(document)
        self.assertEqual(move.invoice_line_ids.purchase_line_id, po_old.order_line)
        self.assertEqual(po_old.invoice_status, "invoiced")
        self.assertEqual(po_new.invoice_status, "to invoice")

    def test_no_double_billing_of_the_same_po_quantity(self):
        po = self._create_po([(self.product_a, 5)])
        move1 = self._import(
            self._create_fiscal_document([{"product": self.product_a, "qty": 5}])
        )
        move2 = self._import(
            self._create_fiscal_document([{"product": self.product_a, "qty": 5}])
        )
        self.assertEqual(move1.invoice_line_ids.purchase_line_id, po.order_line)
        self.assertFalse(move2.invoice_line_ids.purchase_line_id)
        self.assertEqual(po.order_line.qty_invoiced, 5)

    def test_without_purchase_order_nothing_changes(self):
        document = self._create_fiscal_document(
            [{"product": self.product_a, "qty": 10, "uom": self.uom_kg}]
        )
        move = self._import(document)
        line = move.invoice_line_ids
        self.assertFalse(line.purchase_line_id)
        self.assertFalse(move.invoice_origin)
        self.assertEqual(line.quantity, 10)
        self.assertEqual(line.price_unit, 38.0)
        self.assertEqual(line.product_uom_id, self.uom_kg)
        self.assertEqual(move.amount_total, document.fiscal_amount_total)

    def test_po_line_uom_is_kept_over_fiscal_uom(self):
        po = self._create_po([(self.product_a, 10)])
        document = self._create_fiscal_document(
            [{"product": self.product_a, "qty": 10, "uom": self.uom_kg}]
        )
        move = self._import(document)
        line = move.invoice_line_ids
        self.assertEqual(line.purchase_line_id, po.order_line)
        self.assertEqual(line.product_uom_id, self.uom_unit)
        self.assertEqual(
            line.product_uom_id.category_id,
            po.order_line.product_uom.category_id,
        )
        self.assertEqual(po.order_line.qty_invoiced, 10)
        self.assertEqual(move.amount_total, document.fiscal_amount_total)

    def test_import_into_bill_from_po_has_no_duplicates(self):
        po = self._create_po([(self.product_a, 10)])
        po.action_create_invoice()
        bill = po.invoice_ids
        self.assertEqual(len(bill.invoice_line_ids), 1)
        pol = po.order_line
        document = self._create_fiscal_document(
            [{"product": self.product_a, "qty": 10}]
        )
        bill.fiscal_document_id = document
        move = self._import(document, move_id=bill.id)
        self.assertEqual(move, bill)
        self.assertEqual(len(move.invoice_line_ids), 1)
        self.assertEqual(move.invoice_line_ids.purchase_line_id, pol)
        self.assertEqual(
            move.invoice_line_ids.fiscal_document_line_id.document_id, document
        )
        self.assertEqual(pol.qty_invoiced, 10)
        self.assertEqual(move.amount_total, document.fiscal_amount_total)
        self.assertEqual(po.invoice_ids, bill)

    def test_import_into_bill_from_po_with_latam_documents(self):
        """The LATAM document number must not block the import into a bill
        that already has a fiscal document."""
        if "l10n_latam.document.type" not in self.env:
            self.skipTest("l10n_latam_invoice_document not installed")
        journal = self.company_data["default_journal_purchase"]
        journal.l10n_latam_use_documents = True
        self.test_import_into_bill_from_po_has_no_duplicates()
