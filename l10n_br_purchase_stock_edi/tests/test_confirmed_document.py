# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError

from .common import StockEdiCase


class TestConfirmedDocument(StockEdiCase):
    """The way out of the refusal of the bill is also open to the document that
    was already confirmed, or imported by the former assistant, while it has
    no bill."""

    def _confirmed(self, state="autorizada"):
        """A document confirmed before anyone decided the origin of its lines."""
        self._resolve_product()
        self.document.write({"state_edoc": state})
        self.assertFalse(self.line.import_origin_state)
        return self._rows(fiscal_document_id=self.document.id)

    def test_the_refusal_of_the_bill_has_a_way_out_after_the_confirmation(self):
        note = self._confirmed()
        with self.assertRaisesRegex(UserError, "no order and no receipt"):
            self.document.action_generate_invoice()

        self.assertTrue(note)
        note.action_no_order()
        note.action_create_receipt()

        self.assertTrue(self.line.import_stock_move_id)
        self.assertEqual(self.document.state_edoc, "autorizada")
        self.assertTrue(self.document.action_generate_invoice())

    def test_without_order_decided_on_the_confirmed_document(self):
        note = self._confirmed("a_enviar")

        note.action_no_order()

        self.assertEqual(self.line.import_origin_state, "no_order")
        with self.assertRaisesRegex(UserError, "no order and no receipt"):
            self.document.action_generate_invoice()

    def test_the_mark_of_the_manager_on_the_confirmed_document(self):
        note = self._confirmed()
        note.action_no_order()
        manager = self.env["res.users"].create(
            {
                "name": "Manager",
                "login": "manager-confirmed",
                "company_ids": [(6, 0, self.company.ids)],
                "company_id": self.company.id,
                "groups_id": [
                    (6, 0, [self.env.ref("purchase.group_purchase_manager").id])
                ],
            }
        )

        note.with_user(manager).with_context(
            allowed_company_ids=manager.company_ids.ids
        ).action_no_stock_entry()

        self.assertTrue(self.line.sudo().import_no_stock_entry)
        self.assertTrue(self.document.action_generate_invoice())

    def test_a_legacy_document_has_the_whole_way_out(self):
        """Confirmed and with the origin empty, as the former assistant left it."""
        note = self._confirmed()
        self.assertEqual(note.line_state, "none")

        note.action_no_order()
        note.action_create_receipt()
        self.assertTrue(self.document.action_generate_invoice())

    def test_the_document_with_a_bill_stays_out(self):
        note = self._confirmed()
        note.action_no_order()
        note.action_create_receipt()
        self.document.action_generate_invoice()

        self.assertFalse(self.document.edi_can_match_orders)
        self.assertFalse(self._rows(fiscal_document_id=self.document.id))
        with self.assertRaisesRegex(UserError, "closed or already has a bill"):
            self.Match._editable_document(self.line)

    def test_the_cancelled_document_is_not_on_the_screen(self):
        self._confirmed("cancelada")

        self.assertFalse(self.document.edi_can_match_orders)
        self.assertFalse(self._rows(fiscal_document_id=self.document.id))
