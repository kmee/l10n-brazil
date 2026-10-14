# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import os

from odoo import fields
from odoo.exceptions import UserError
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
        cls.uom_dozen = cls.env.ref("uom.product_uom_dozen")
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
        for item in products_qty:
            item[0].purchase_method = "purchase"
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

    def test_fiscal_data_is_not_changed_by_the_link(self):
        """Only purchase_line_id is written: the quantity, price and UoM of the
        document are kept and the PO line gets its quantity converted by the
        standard qty_invoiced computation (same UoM category)."""
        po = self._create_po([(self.product_a, 24)])
        document = self._create_fiscal_document(
            [
                {
                    "product": self.product_a,
                    "qty": 2,
                    "price": 456.0,
                    "uom": self.uom_dozen,
                }
            ]
        )
        move = self._import(document)
        line = move.invoice_line_ids
        self.assertEqual(line.purchase_line_id, po.order_line)
        self.assertEqual(line.product_uom_id, self.uom_dozen)
        self.assertEqual(line.quantity, 2)
        self.assertEqual(line.price_unit, 456.0)
        fiscal_line = document.fiscal_line_ids
        self.assertEqual(fiscal_line.quantity, 2)
        self.assertEqual(fiscal_line.price_unit, 456.0)
        self.assertEqual(po.order_line.qty_invoiced, 24)
        self.assertEqual(move.amount_total, document.fiscal_amount_total)

    def test_uom_category_mismatch_is_not_linked(self):
        po = self._create_po([(self.product_a, 10)])
        document = self._create_fiscal_document(
            [{"product": self.product_a, "qty": 10, "uom": self.uom_kg}]
        )
        move = self._import(document)
        line = move.invoice_line_ids
        self.assertFalse(line.purchase_line_id)
        self.assertEqual(line.product_uom_id, self.uom_kg)
        self.assertEqual(po.order_line.qty_invoiced, 0)

    def test_link_before_receipt_with_receive_policy(self):
        po = self._create_po([(self.product_a, 10)])
        self.product_a.purchase_method = "receive"
        self.assertEqual(po.order_line.qty_to_invoice, 0)
        move = self._import(
            self._create_fiscal_document([{"product": self.product_a, "qty": 10}])
        )
        self.assertEqual(move.invoice_line_ids.purchase_line_id, po.order_line)
        self.assertEqual(po.order_line.qty_invoiced, 10)

    def test_only_a_purchase_line_with_enough_quantity_is_linked(self):
        po1 = self._create_po([(self.product_a, 30)])
        po2 = self._create_po([(self.product_a, 100)])
        po2.date_order = fields.Datetime.add(po1.date_order, days=3)
        move = self._import(
            self._create_fiscal_document([{"product": self.product_a, "qty": 100}])
        )
        self.assertEqual(move.invoice_line_ids.purchase_line_id, po2.order_line)
        self.assertEqual(po1.order_line.qty_invoiced, 0)
        # nothing left with enough quantity: no link, no split
        move2 = self._import(
            self._create_fiscal_document([{"product": self.product_a, "qty": 40}])
        )
        self.assertFalse(move2.invoice_line_ids.purchase_line_id)

    def test_xped_match_never_falls_back_to_another_order(self):
        po1 = self._create_po([(self.product_a, 5)], partner_order="PED-A")
        po2 = self._create_po([(self.product_a, 50)])
        document = self._create_fiscal_document(
            [{"product": self.product_a, "qty": 20, "xped": "PED-A"}]
        )
        move = self._import(document)
        self.assertFalse(move.invoice_line_ids.purchase_line_id)
        self.assertEqual(po1.order_line.qty_invoiced, 0)
        self.assertEqual(po2.order_line.qty_invoiced, 0)

    def test_unknown_xped_falls_back_to_product(self):
        po = self._create_po([(self.product_a, 5)])
        document = self._create_fiscal_document(
            [{"product": self.product_a, "qty": 5, "xped": "NOT-A-PO"}]
        )
        move = self._import(document)
        self.assertEqual(move.invoice_line_ids.purchase_line_id, po.order_line)

    def test_import_into_bill_from_po_is_refused_and_changes_nothing(self):
        analytic = self._create_analytic_account("Bill from PO")
        po = self._create_po([(self.product_a, 10), (self.product_b, 4)])
        po.order_line.analytic_distribution = {str(analytic.id): 100.0}
        po.action_create_invoice()
        bill = po.invoice_ids
        self.assertEqual(len(bill.invoice_line_ids), 2)
        before = {
            line.id: (
                line.product_id,
                line.quantity,
                line.price_unit,
                line.purchase_line_id,
                line.analytic_distribution,
            )
            for line in bill.invoice_line_ids
        }
        total = bill.amount_total
        document = self._create_fiscal_document(
            [{"product": self.product_a, "qty": 10}]
        )
        with self.assertRaisesRegex(UserError, "already has lines from purchase"):
            self._import(document, move_id=bill.id)
        self.assertEqual(bill.amount_total, total)
        self.assertEqual(len(bill.invoice_line_ids), 2)
        after = {
            line.id: (
                line.product_id,
                line.quantity,
                line.price_unit,
                line.purchase_line_id,
                line.analytic_distribution,
            )
            for line in bill.invoice_line_ids
        }
        self.assertEqual(before, after)
        self.assertTrue(
            all(line.analytic_distribution for line in bill.invoice_line_ids)
        )
        self.assertEqual(po.order_line[0].qty_invoiced, 10)

    def test_import_a_real_nfe_xml_through_the_wizard(self):
        if "nfe40_dup" not in self.env["l10n_br_fiscal.document"]._fields:
            self.skipTest("l10n_br_nfe not installed")
        from odoo.addons import l10n_br_nfe

        path = os.path.join(
            l10n_br_nfe.__path__[0],
            "tests",
            "nfe",
            "v4_00",
            "leiauteNFe",
            "NFe35200681583054000129550010000000012760018057-nf-e.xml",
        )
        with open(path, "rb") as xml_file:
            xml = xml_file.read()
        wizard = (
            self.env["l10n_br_fiscal.document.import.wizard"]
            .sudo()
            .create(
                {
                    "company_id": self.company_data["company"].id,
                    "file": base64.b64encode(xml),
                }
            )
        )
        wizard._onchange_file()
        product_1 = self.env["product.product"].search(
            [("default_code", "=", "E-COM07")], limit=1
        )
        product_2 = self.env["product.product"].search(
            [("default_code", "=", "FURN_8855")], limit=1
        )
        self.assertTrue(product_1 and product_2)
        po = self.env["purchase.order"].create(
            {
                "partner_id": wizard.issuer_partner_id.id,
                "company_id": self.company_data["company"].id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": prod.id,
                            "product_qty": 1,
                            "price_unit": 1.0,
                            "name": prod.name,
                            "product_uom": prod.uom_id.id,
                        },
                    )
                    for prod in (product_1, product_2)
                ],
            }
        )
        po.button_confirm()
        wizard.action_import_and_open_move()
        move = self.env["account.move"].search(
            [("fiscal_document_id", "=", wizard.document_id.id)]
        )
        self.assertEqual(len(move), 1)
        self.assertEqual(move.invoice_line_ids.purchase_line_id, po.order_line)
        self.assertAlmostEqual(move.amount_total, 4147.25, places=2)
        for line in move.invoice_line_ids:
            self.assertEqual(line.fiscal_document_line_id.fiscal_quantity, 1.0)
            self.assertEqual(line.fiscal_document_line_id.uot_id, self.uom_unit)
        by_code = {
            line.product_id.default_code: line.fiscal_document_line_id
            for line in move.invoice_line_ids
        }
        self.assertAlmostEqual(by_code["E-COM07"].price_unit, 320.0)
        self.assertAlmostEqual(by_code["FURN_8855"].price_unit, 3645.0)
        self.assertAlmostEqual(by_code["FURN_8855"].ipi_value, 182.25)
        self.assertAlmostEqual(by_code["FURN_8855"].icms_value, 459.27)

    def _create_analytic_account(self, name):
        plan = self.env["account.analytic.plan"].create({"name": f"Plan {name}"})
        return self.env["account.analytic.account"].create(
            {"name": name, "plan_id": plan.id}
        )

    def test_link_copies_the_po_line_analytic_distribution(self):
        analytic = self._create_analytic_account("PO analytic")
        po = self._create_po([(self.product_a, 5)])
        distribution = {str(analytic.id): 100.0}
        po.order_line.analytic_distribution = distribution
        move = self._import(
            self._create_fiscal_document([{"product": self.product_a, "qty": 5}])
        )
        line = move.invoice_line_ids
        self.assertEqual(line.purchase_line_id, po.order_line)
        self.assertEqual(line.analytic_distribution, distribution)

    def test_link_keeps_an_existing_analytic_distribution(self):
        """A bill line that already has an analytic distribution is never
        overwritten by the one of the purchase order line."""
        analytic = self._create_analytic_account("PO analytic")
        other = self._create_analytic_account("Bill analytic")
        po = self._create_po([(self.product_a, 5)])
        po.order_line.analytic_distribution = {str(analytic.id): 100.0}
        move = self._import(
            self._create_fiscal_document([{"product": self.product_a, "qty": 5}])
        )
        line = move.invoice_line_ids
        line.analytic_distribution = {str(other.id): 100.0}
        # relink: drop the link and run the matching again on the same line
        line.purchase_line_id = False
        self.env["account.move"].sudo()._po_link_new_lines(
            move, line.fiscal_document_line_id.document_id
        )
        self.assertEqual(line.purchase_line_id, po.order_line)
        self.assertEqual(line.analytic_distribution, {str(other.id): 100.0})
