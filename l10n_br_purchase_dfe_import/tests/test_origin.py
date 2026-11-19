# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal_dfe_import.tests.common import KEY_2

from .common import PurchaseImportCase


class TestOrigin(PurchaseImportCase):
    def test_declared_reference_resolves_the_origin(self):
        order = self._order()
        self.line.write({"partner_order": order.name, "partner_order_line": "1"})
        self._resolve_product()

        self.assertEqual(self.line.import_purchase_line_id, order.order_line)
        self.assertEqual(self.line.import_origin_state, "resolved")

    def test_only_open_line_of_the_product_is_suggested(self):
        order = self._order()
        self._resolve_product()

        self.assertEqual(self.line.import_purchase_line_id, order.order_line)
        self.assertEqual(self.line.import_origin_state, "suggested")
        # what the supplier declared stays as it came
        self.assertFalse(self.line.partner_order)

    def test_two_candidates_stay_pending(self):
        self._order()
        self._order()
        self._resolve_product()

        self.assertFalse(self.line.import_purchase_line_id)
        self.assertEqual(self.line.import_origin_state, "pending")

    def test_a_document_without_operation_still_gets_the_suggestion(self):
        self.document.fiscal_operation_id = False
        order = self._order()
        self._resolve_product()

        self.assertEqual(self.line.import_purchase_line_id, order.order_line)
        self.assertEqual(self.line.import_origin_state, "suggested")

    def test_supplier_without_open_orders_leaves_no_state(self):
        self._resolve_product()

        self.assertFalse(self.line.import_origin_state)

    def test_order_of_another_supplier_is_not_a_candidate(self):
        self._order(partner=self.company.partner_id)
        self._resolve_product()

        self.assertFalse(self.line.import_origin_state)

    def test_a_decision_is_never_replaced(self):
        self._order()
        self._resolve_product()
        self.line.write(
            {"import_purchase_line_id": False, "import_origin_state": "no_order"}
        )
        self.line._suggest_import_origin()
        self.assertEqual(self.line.import_origin_state, "no_order")
        self.assertFalse(self.line.import_purchase_line_id)

        self.line.import_origin_state = "resolved"
        self.line._suggest_import_origin()
        self.assertEqual(self.line.import_origin_state, "resolved")

    def test_choosing_the_order_line_resolves_it(self):
        order = self._order()
        self._order()
        self._resolve_product()

        self.line.import_purchase_line_id = order.order_line

        self.assertEqual(self.line.import_origin_state, "resolved")

    def test_confirm_origins_resolves_the_suggestions(self):
        self._order()
        self._resolve_product()
        self.assertTrue(self.document.has_suggested_import_origin)

        self.document.action_confirm_import_origins()

        self.assertEqual(self.line.import_origin_state, "resolved")
        self.assertFalse(self.document.has_suggested_import_origin)

    def test_balance_discounts_the_claims_of_other_documents(self):
        order = self._order(quantity=10)
        other, _errors = self.Document.dfe_import_files([("nfe.xml", self._xml(KEY_2))])
        other_line = other.fiscal_line_ids
        other_line.write({"quantity": 10, "uom_id": self.unit.id})
        other_line.import_purchase_line_id = order.order_line
        self.assertEqual(other_line.import_origin_state, "resolved")
        self._resolve_product()

        # the other document holds all 10: nothing is left for this one
        self.assertFalse(self.line.import_purchase_line_id)
        self.assertEqual(self.line.import_origin_state, "pending")
        self.assertFalse(self._rows(purchase_line_id=order.order_line.id))

        other_line.quantity = 9
        self.line._suggest_import_origin()
        self.assertEqual(self.line.import_origin_state, "suggested")
        row = self._rows(purchase_line_id=order.order_line.id)
        self.assertEqual(row.open_quantity, 1)

    def test_resolved_origin_takes_the_destination_of_the_order(self):
        order = self._order()
        destination = self.env.ref("l10n_br_fiscal.fo_compras_compras_uso_consumo")
        order.order_line.fiscal_operation_line_id = destination
        self._resolve_product()
        self.assertNotEqual(self.line.fiscal_operation_line_id, destination)

        self.document.action_confirm_import_origins()

        self.assertEqual(self.line.fiscal_operation_line_id, destination)

    def test_the_destination_is_applied_after_the_operation_is_suggested(self):
        # the supplier and the product of the file are known from a first import
        first, _errors = self.Document.dfe_import_files([("nfe.xml", self._xml(KEY_2))])
        self.product = first.fiscal_line_ids.product_id
        order = self._order(partner=first.partner_id)
        first.unlink()
        destination = self.env.ref("l10n_br_fiscal.fo_compras_compras_uso_consumo")
        order.order_line.fiscal_operation_line_id = destination
        xml = self._xml(KEY_2).replace(
            b"</prod>",
            b"<xPed>%s</xPed><nItemPed>1</nItemPed></prod>" % order.name.encode(),
            1,
        )

        documents, errors = self.Document.dfe_import_files([("nfe.xml", xml)])

        line = documents.fiscal_line_ids
        self.assertFalse(errors)
        self.assertEqual(line.import_origin_state, "resolved")
        self.assertEqual(line.fiscal_operation_line_id, destination)

    def test_destination_does_not_replace_a_manual_choice(self):
        order = self._order()
        destination = self.env.ref("l10n_br_fiscal.fo_compras_compras_uso_consumo")
        order.order_line.fiscal_operation_line_id = destination
        asset = self.env.ref("l10n_br_fiscal.fo_compras_compras_ativo")
        self._resolve_product()
        self.line.fiscal_operation_line_id = asset

        self.document.action_confirm_import_origins()

        self.assertEqual(self.line.fiscal_operation_line_id, asset)

    def test_order_line_name_shows_the_order(self):
        order = self._order()

        self.assertIn(order.name, order.order_line.display_name)
        found = self.env["purchase.order.line"].name_search(order.name)
        self.assertIn(order.order_line.id, [line_id for line_id, _name in found])

    def test_generate_invoice_refuses_an_undecided_origin(self):
        self._order()
        self._resolve_product()

        with self.assertRaisesRegex(UserError, "not decided"):
            self.document.action_generate_invoice()
