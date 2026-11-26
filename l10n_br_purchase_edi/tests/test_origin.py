# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase


class TestImportOrigin(TransactionCase):
    """The three sample notes of the demo data, one in each step of the life
    cycle (see ``demo/purchase_edi_demo.xml``)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Match = cls.env["l10n_br_purchase_edi.match"]
        cls.order = cls.env.ref("l10n_br_purchase_edi.demo_order_confirmed")
        cls.quotation = cls.env.ref("l10n_br_purchase_edi.demo_order_quotation")
        cls.note_declared = cls._document(cls, "2001")
        cls.note_quoted = cls._document(cls, "2002")
        cls.note_without = cls._document(cls, "2003")

    def _document(self, number):
        return self.env["l10n_br_fiscal.document"].search(
            [
                ("document_number", "=", number),
                ("partner_id", "=", self.env.ref("l10n_br_base.res_partner_dell").id),
            ],
            limit=1,
        )

    def test_declared_order_resolves_and_invoices(self):
        line = self.note_declared.fiscal_line_ids
        self.assertEqual(line.import_origin_state, "resolved")
        self.assertEqual(line.import_purchase_line_id, self.order.order_line)
        bill = self.note_declared.move_ids
        self.assertEqual(bill.state, "posted")
        self.assertEqual(bill.invoice_line_ids.purchase_line_id, self.order.order_line)
        self.assertEqual(self.order.order_line.qty_invoiced, 5)

    def test_quotation_waits_then_is_suggested(self):
        line = self.note_quoted.fiscal_line_ids
        self.assertFalse(line.import_purchase_line_id)
        # the supplier has an order, already invoiced, and no open line for it
        self.assertEqual(line.import_origin_state, "pending")
        self.assertTrue(self.note_quoted.edi_can_match_orders)
        self.quotation.button_confirm()
        self.assertEqual(line.import_origin_state, "suggested")
        self.assertEqual(line.import_purchase_line_id, self.quotation.order_line)
        self.assertTrue(self.note_quoted.has_suggested_import_origin)

    def test_post_refused_while_origin_is_suggested(self):
        self.quotation.button_confirm()
        bill = self.note_quoted.move_ids
        with self.assertRaises(UserError):
            bill.action_post()

    def test_confirm_origins_links_the_draft_bill(self):
        self.quotation.button_confirm()
        bill = self.note_quoted.move_ids
        self.assertFalse(bill.invoice_line_ids.purchase_line_id)
        bill.action_confirm_import_origins()
        line = self.note_quoted.fiscal_line_ids
        self.assertEqual(line.import_origin_state, "resolved")
        self.assertEqual(
            bill.invoice_line_ids.purchase_line_id, self.quotation.order_line
        )
        self.assertEqual(self.quotation.order_line.qty_invoiced, 5)
        bill.action_post()
        self.assertEqual(bill.state, "posted")

    def test_undo_unlinks_the_draft_bill(self):
        self.quotation.button_confirm()
        bill = self.note_quoted.move_ids
        bill.action_confirm_import_origins()
        line = self.note_quoted.fiscal_line_ids
        line.write({"import_purchase_line_id": False})
        self.assertEqual(line.import_origin_state, "pending")
        self.assertFalse(bill.invoice_line_ids.purchase_line_id)
        self.assertEqual(self.quotation.order_line.qty_invoiced, 0)

    def test_without_order(self):
        line = self.note_without.fiscal_line_ids
        self.assertEqual(line.import_origin_state, "no_order")
        self.assertFalse(line.import_purchase_line_id)
        self.assertFalse(self.note_without.move_ids.invoice_line_ids.purchase_line_id)
        # a decision of a person is not replaced by a new suggestion
        line._suggest_import_origin()
        self.assertEqual(line.import_origin_state, "no_order")

    def test_split_order_lines_of_the_item(self):
        line = self.note_declared.fiscal_line_ids
        company = self.order.company_id

        def order_of(partner):
            return self.env["purchase.order"].create(
                {
                    "partner_id": partner.id,
                    "company_id": company.id,
                    "order_line": [
                        Command.create(
                            {
                                "product_id": line.product_id.id,
                                "name": line.product_id.name,
                                "product_qty": 2,
                                "price_unit": 140.0,
                            }
                        )
                    ],
                }
            )

        # the order was split in two lines and invoiced as one item
        split = order_of(self.order.partner_id).order_line
        line.import_split_purchase_line_ids = split
        self.assertEqual(line.import_split_purchase_line_ids, split)
        self.assertEqual(line.import_purchase_line_id, self.order.order_line)
        other_supplier = order_of(self.env.ref("l10n_br_base.res_partner_amd"))
        with self.assertRaises(ValidationError):
            line.import_split_purchase_line_ids = other_supplier.order_line

    def test_match_screen(self):
        self.quotation.button_confirm()
        self.env.flush_all()
        rows = self.Match.search([("fiscal_document_id", "=", self.note_quoted.id)])
        self.assertEqual(rows.kind, "note")
        self.assertEqual(rows.line_state, "suggested")
        orders = self.Match.search([("purchase_order_id", "=", self.quotation.id)])
        self.assertEqual(orders.kind, "order")
        self.assertEqual(orders.open_quantity, 5)
        # a person picks the order line on the screen
        (rows | orders).action_match()
        line = self.note_quoted.fiscal_line_ids
        self.assertEqual(line.import_origin_state, "resolved")
        self.assertEqual(
            self.note_quoted.move_ids.invoice_line_ids.purchase_line_id,
            self.quotation.order_line,
        )
