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

    def test_a_consumable_without_order_needs_the_receipt_by_default(self):
        self.product.is_storable = False
        self.assertEqual(self.company.import_stock_entry_policy, "goods")
        note = self._no_order()

        with self.assertRaisesRegex(UserError, "no order and no receipt"):
            self.document.action_generate_invoice()

        note.action_create_receipt()
        picking = self.line.import_stock_move_id.picking_id
        self.assertEqual(picking.state, "assigned")
        self.assertTrue(self.document.action_generate_invoice())

    def test_the_mark_of_the_manager_releases_a_consumable(self):
        self.product.is_storable = False
        self._no_order()
        manager = self._user("manager-consu", "purchase.group_purchase_manager")
        self._rows(fiscal_document_id=self.document.id).with_user(manager).with_context(
            allowed_company_ids=manager.company_ids.ids
        ).action_no_stock_entry()

        self.assertTrue(self.document.action_generate_invoice())

    def test_the_policy_storable_lets_a_consumable_go_on(self):
        self.company.import_stock_entry_policy = "storable"
        self.product.is_storable = False
        self._no_order()
        self.assertTrue(self.document.action_generate_invoice())

        self.product.is_storable = True
        other = self._imported_document(lines=[{"price_unit": 10.0}])
        self._resolve_product(other.fiscal_line_ids)
        with self.assertRaisesRegex(UserError, "no order and no receipt"):
            other.action_generate_invoice()

    def test_the_policy_none_asks_nothing(self):
        self.company.import_stock_entry_policy = "none"
        self._no_order()

        self.assertFalse(self.line._import_needs_stock_entry())
        self.assertTrue(self.document.action_generate_invoice())

    def test_a_service_is_never_asked(self):
        service = self.env["product.product"].create(
            {"name": "Service", "type": "service"}
        )
        for policy in ("goods", "storable", "none"):
            self.company.import_stock_entry_policy = policy
            document = self._imported_document(lines=[{"price_unit": 10.0}])
            line = document.fiscal_line_ids
            line._apply_import_depara(
                product=service, uom=self.unit, fiscal_operation=self.operation
            )
            self.assertFalse(line._import_needs_stock_entry(), policy)

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

    def test_a_fresh_consumable_goes_on_with_the_policy_storable(self):
        self.company.import_stock_entry_policy = "storable"
        self.product.is_storable = False
        self._fresh_note()
        self.assertTrue(self.document.action_generate_invoice())

    def test_a_fresh_consumable_is_refused_by_default(self):
        self.product.is_storable = False
        self._fresh_note()
        with self.assertRaisesRegex(UserError, "no order and no receipt"):
            self.document.action_generate_invoice()

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
        self.assertIn(
            self.line,
            self.Match.search(domain + [("kind", "=", "note")]).fiscal_line_id,
        )
        self.product.type = "service"
        self.env.flush_all()
        self.assertNotIn(
            self.line,
            self.Match.search(domain + [("kind", "=", "note")]).fiscal_line_id,
        )

    def _pending_domain(self):
        view = self.env.ref("l10n_br_purchase_stock_edi.document_match_search")
        node = etree.fromstring(self.Match.get_view(view.id, "search")["arch"])
        return safe_eval(
            node.xpath("//filter[@name='pending_or_suggested']")[0].get("domain")
        ) + [("kind", "=", "note")]

    def test_the_pending_filter_follows_the_policy_of_the_company(self):
        self._fresh_note()
        domain = self._pending_domain()
        expected = {
            # policy: (storable product, consumable without inventory control)
            "goods": (True, True),
            "storable": (True, False),
            "none": (False, False),
        }
        for policy, (storable, consumable) in expected.items():
            self.company.import_stock_entry_policy = policy
            for is_storable, found in ((True, storable), (False, consumable)):
                self.product.is_storable = is_storable
                self.env.flush_all()
                rows = self.Match.search(domain)
                self.assertEqual(
                    self.line in rows.fiscal_line_id,
                    found,
                    f"{policy}, storable={is_storable}",
                )
                # the same rule that the invoice applies
                self.assertEqual(self.line._import_product_needs_receipt(), found)
                self.assertEqual(
                    self.line
                    in self.Match.search(
                        [("import_needs_receipt", "!=", True), ("kind", "=", "note")]
                    ).fiscal_line_id,
                    not found,
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
