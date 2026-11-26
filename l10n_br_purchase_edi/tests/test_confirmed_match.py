# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError

from .common import PurchaseEdiCase


class TestConfirmedMatch(PurchaseEdiCase):
    """The reconciliation reaches the imported document that was already
    confirmed, while it has no bill and was not cancelled."""

    def _set_state(self, state):
        self.document.write({"state_edoc": state})

    def _open(self):
        domain = self.document.action_open_origin_match()["domain"]
        self.env.flush_all()
        return self.Match.search(domain)

    def test_a_confirmed_document_without_bill_is_on_the_screen(self):
        order = self._order()
        self._resolve_product()
        self._set_state("autorizada")

        self.assertTrue(self.document.edi_can_match_orders)
        rows = self._open()

        self.assertTrue(rows.filtered(lambda row: row.kind == "note"))
        self.assertEqual(
            rows.filtered(lambda row: row.kind == "order").purchase_line_id,
            order.order_line,
        )

    def test_a_confirmed_document_takes_every_decision_of_the_screen(self):
        order = self._order()
        self._resolve_product()
        self._set_state("autorizada")
        operation_line = self.line.fiscal_operation_line_id
        note = self._rows(fiscal_document_id=self.document.id)

        (note | self._rows(purchase_line_id=order.order_line.id)).action_match()
        self.assertEqual(self.line.import_origin_state, "resolved")
        # the fiscal data of a confirmed document are left as they were
        self.assertEqual(self.line.fiscal_operation_line_id, operation_line)
        self.assertEqual(self.document.state_edoc, "autorizada")

        self._rows(fiscal_document_id=self.document.id).action_undo()
        self.assertEqual(self.line.import_origin_state, "pending")

        self._rows(fiscal_document_id=self.document.id).action_no_order()
        self.assertEqual(self.line.import_origin_state, "no_order")

    def test_a_document_with_a_bill_is_out_of_the_screen(self):
        self._resolve_product()
        self.line.import_origin_state = "no_order"
        self.document.action_generate_invoice()
        self._set_state("autorizada")

        self.assertTrue(self.document.move_ids)
        self.assertFalse(self.document.edi_can_match_orders)
        self.assertFalse(self._rows(fiscal_document_id=self.document.id))
        with self.assertRaisesRegex(UserError, "closed or already has a bill"):
            self.Match._editable_document(self.line)

    def test_a_cancelled_denied_or_invalidated_document_is_out_of_the_screen(self):
        self._resolve_product()
        for state in ("cancelada", "denegada", "inutilizada"):
            self._set_state(state)
            self.assertFalse(self.document.edi_can_match_orders, state)
            self.assertFalse(self._rows(fiscal_document_id=self.document.id), state)
            with self.assertRaisesRegex(UserError, "closed or already has a bill"):
                self.Match._editable_document(self.line)
