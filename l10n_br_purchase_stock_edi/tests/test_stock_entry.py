# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

from .common import StockEdiCase


class TestStockEntry(StockEdiCase):
    def _no_order(self):
        self._resolve_product()
        note = self._rows(fiscal_document_id=self.document.id)
        note.action_no_order()
        return note

    def _user(self, login, *group_xmlids):
        groups = [self.env.ref(xmlid).id for xmlid in group_xmlids]
        return self.env["res.users"].create(
            {
                "name": "Buyer",
                "login": login,
                "company_ids": [(6, 0, self.company.ids)],
                "company_id": self.company.id,
                "groups_id": [(6, 0, groups)],
            }
        )

    def test_without_order_a_stockable_product_needs_the_stock_entry(self):
        self._no_order()

        with self.assertRaisesRegex(UserError, "no order and no receipt"):
            self.document.action_generate_invoice()

    def test_a_consumable_goes_on_without_order_and_receipt(self):
        self.product.is_storable = False
        self._no_order()

        action = self.document.action_generate_invoice()

        self.assertTrue(action["res_id"])

    def test_the_receipt_created_from_the_document_unlocks_it(self):
        note = self._no_order()

        action = note.action_create_receipt()

        picking = self.env["stock.picking"].browse(action["res_id"])
        move = picking.move_ids
        self.assertEqual(picking.picking_type_id.code, "incoming")
        self.assertEqual(picking.state, "assigned")
        self.assertEqual((move.product_id, move.product_uom), (self.product, self.unit))
        self.assertEqual(move.product_uom_qty, self.line.quantity)
        self.assertEqual(move.price_unit, self.line.price_unit)
        self.assertEqual(self.line.import_stock_move_id, move)
        self.assertEqual(self.line.import_origin_state, "no_order")
        self.assertTrue(self.document.action_generate_invoice())

    def test_the_receipt_is_for_stockable_lines_without_order_and_receipt(self):
        self._resolve_product()
        note = self._rows(fiscal_document_id=self.document.id)
        with self.assertRaisesRegex(UserError, "without order"):
            note.action_create_receipt()

        note.action_no_order()
        note.action_create_receipt()
        with self.assertRaisesRegex(UserError, "without order"):
            self._rows(fiscal_document_id=self.document.id).action_create_receipt()

    def _fresh_note(self):
        """Just imported, never seen by the reconciliation: no origin state."""
        self._resolve_product()
        self.assertFalse(self.line.import_origin_state)
        self.assertFalse(self.line.import_purchase_line_id)
        return self._rows(fiscal_document_id=self.document.id)

    def test_a_fresh_stockable_without_order_is_refused(self):
        self._fresh_note()

        with self.assertRaisesRegex(UserError, "no order and no receipt"):
            self.document.action_generate_invoice()

    def test_the_receipt_of_a_fresh_stockable_unlocks_it(self):
        note = self._fresh_note()
        with self.assertRaisesRegex(UserError, "without order"):
            note.action_create_receipt()

        note.action_no_order()
        note.action_create_receipt()

        self.assertTrue(self.line.import_stock_move_id)
        self.assertEqual(self.line.import_origin_state, "no_order")
        self.assertTrue(self.document.action_generate_invoice())

    def test_the_mark_of_the_manager_on_a_fresh_stockable_unlocks_it(self):
        rows = self._fresh_note()
        manager = self._user("manager-fresh", "purchase.group_purchase_manager")
        with self.assertRaisesRegex(UserError, "marked as without order"):
            rows.with_user(manager).with_context(
                allowed_company_ids=manager.company_ids.ids
            ).action_no_stock_entry()
        rows.action_no_order()

        rows.with_user(manager).with_context(
            allowed_company_ids=manager.company_ids.ids
        ).action_no_stock_entry()

        self.assertTrue(self.line.sudo().import_no_stock_entry)
        self.assertEqual(self.line.import_origin_state, "no_order")
        self.assertTrue(self.document.action_generate_invoice())

    def test_a_fresh_consumable_and_a_service_go_on(self):
        self.product.is_storable = False
        self._fresh_note()
        self.assertTrue(self.document.action_generate_invoice())

        service = self.env["product.product"].create(
            {"name": "Service", "type": "service"}
        )
        other = self._imported_document(lines=[{"price_unit": 10.0}])
        other.fiscal_line_ids._apply_import_depara(
            product=service, uom=self.unit, fiscal_operation=self.operation
        )
        self.assertFalse(other.fiscal_line_ids.import_origin_state)
        self.assertTrue(other.action_generate_invoice())

    def test_a_line_with_an_order_is_not_affected(self):
        order = self._order(quantity=10)
        self._resolve_product()
        self.line.import_purchase_line_id = order.order_line

        self.assertEqual(self.line.import_origin_state, "resolved")
        self.assertFalse(self.line._import_needs_stock_entry())
        self.assertTrue(self.document.action_generate_invoice())

    def test_a_pending_origin_with_no_candidate_is_refused(self):
        self._fresh_note()
        self.line.import_origin_state = "pending"
        self.assertFalse(self.line.import_origin_candidate_ids)

        with self.assertRaisesRegex(UserError, "no order and no receipt"):
            self.document.action_generate_invoice()
        rows = self._rows(fiscal_document_id=self.document.id)
        rows.action_no_order()
        rows.action_create_receipt()
        self.assertTrue(self.document.action_generate_invoice())

    def test_the_candidates_are_left_to_the_purchase_rule(self):
        self._order(quantity=10)
        self._order(quantity=10)
        self._resolve_product()

        self.assertEqual(self.line.import_origin_state, "pending")
        self.assertFalse(self.line._import_needs_stock_entry())
        with self.assertRaisesRegex(UserError, "not decided yet"):
            self.document.action_generate_invoice()

    def test_the_document_of_the_company_and_the_return_are_not_a_purchase(self):
        self._resolve_product()
        self.assertTrue(self.line._import_needs_stock_entry())

        self.document.edoc_purpose = "4"
        self.assertFalse(self.line._import_needs_stock_entry())

        self.document.edoc_purpose = "1"
        self.assertTrue(self.line._import_needs_stock_entry())
        self.document.issuer = "company"
        self.assertFalse(self.line._import_needs_stock_entry())

        # even decided as without order, a document that is not a purchase entry
        # is not asked for the receipt
        self.line.import_origin_state = "no_order"
        self.assertFalse(self.line._import_needs_stock_entry())
        self.document.issuer = "partner"
        self.assertTrue(self.line._import_needs_stock_entry())
        self.document.fiscal_operation_type = "out"
        self.assertFalse(self.line._import_needs_stock_entry())

    def test_a_document_that_was_not_imported_is_not_a_purchase_entry(self):
        self._resolve_product()
        self.document.imported_document = False

        self.assertFalse(self.line._import_needs_stock_entry())

    def test_the_fresh_stockable_is_found_on_the_screen_of_the_buyer(self):
        self._fresh_note()
        self.env.flush_all()
        view = self.env.ref("l10n_br_purchase_stock_edi.document_match_search")
        node = etree.fromstring(self.Match.get_view(view.id, "search")["arch"])
        domain = safe_eval(
            node.xpath("//filter[@name='pending_or_suggested']")[0].get("domain")
        )
        action = self.env.ref("l10n_br_purchase_edi.document_match_buyer_action")
        self.assertIn("search_default_pending_or_suggested", action.context)

        rows = self.Match.search(domain + [("kind", "=", "note")])

        self.assertIn(self.line, rows.fiscal_line_id)
        self.product.is_storable = False
        self.env.flush_all()
        self.assertNotIn(
            self.line,
            self.Match.search(domain + [("kind", "=", "note")]).fiscal_line_id,
        )

    def test_the_receipt_does_not_convert_a_unit_nobody_confirmed(self):
        note = self._no_order()
        self.line.write(
            {"partner_uom_code": "XYZ", "uom_id": False, "import_uom_id": False}
        )

        with self.assertRaisesRegex(UserError, "was not confirmed"):
            note.action_create_receipt()

    def test_only_a_manager_marks_no_stock_entry(self):
        self._no_order()
        buyer = self._user("buyer", "purchase.group_purchase_user")
        manager = self._user("manager", "purchase.group_purchase_manager")
        rows = self._rows(fiscal_document_id=self.document.id)

        with self.assertRaisesRegex(UserError, "Only a purchase manager"):
            rows.with_user(buyer).with_context(
                allowed_company_ids=buyer.company_ids.ids
            ).action_no_stock_entry()
        self.assertFalse(self.line.sudo().import_no_stock_entry)

        rows.with_user(manager).with_context(
            allowed_company_ids=manager.company_ids.ids
        ).action_no_stock_entry()

        self.assertTrue(self.line.sudo().import_no_stock_entry)
        self.assertTrue(self.document.action_generate_invoice())

    def test_creating_the_receipt_does_not_write_on_the_partner(self):
        note = self._no_order()
        before = (self.supplier.name, self.supplier.write_date)

        action = note.action_create_receipt()

        picking = self.env["stock.picking"].browse(action["res_id"])
        self.assertEqual(picking.partner_id, self.supplier)
        self.assertEqual((self.supplier.name, self.supplier.write_date), before)
