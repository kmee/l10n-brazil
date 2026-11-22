# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import PurchaseEdiCase


@tagged("post_install", "-at_install")
class TestMatchAccess(PurchaseEdiCase):
    """The decisions of the screen are controlled writes of the real user: only
    the fields of the origin, on the documents of his companies. The buyer
    decides the origin with no right on the fiscal lines; the product and the
    de-para stay with the fiscal profile."""

    def _user(self, login, groups, companies=None):
        companies = companies or self.company
        user = self._fiscal_user(login, companies)
        user.groups_id = [(5, 0, 0)] + [
            (4, self.env.ref(xmlid).id) for xmlid in ("base.group_user",) + groups
        ]
        return user

    def _as(self, rows, user):
        return rows.with_user(user).with_context(
            allowed_company_ids=user.company_ids.ids
        )

    def _note_rows(self):
        self._resolve_product()
        return self._rows(fiscal_document_id=self.document.id)

    def test_a_user_of_another_company_cannot_decide_the_origin(self):
        rows = self._note_rows()
        user = self._user(
            "other-company-buyer",
            ("l10n_br_fiscal.group_user", "purchase.group_purchase_user"),
            companies=self.other_company,
        )

        for action in ("action_no_order", "action_undo"):
            with self.assertRaises(AccessError):
                getattr(self._as(rows, user), action)()

        self.assertNotEqual(self.line.import_origin_state, "no_order")

    def test_a_user_of_the_company_decides_the_origin(self):
        rows = self._note_rows()
        user = self._user(
            "company-buyer",
            ("l10n_br_fiscal.group_user", "purchase.group_purchase_user"),
        )

        self._as(rows, user).action_no_order()

        self.assertEqual(self.line.import_origin_state, "no_order")

    def test_a_buyer_without_the_fiscal_group_decides_the_origin(self):
        order = self._order()
        rows = self._note_rows()
        rows |= self._rows(purchase_line_id=order.order_line.id, kind="order")
        user = self._user("buyer-only", ("purchase.group_purchase_user",))

        self._as(rows, user).action_match()

        self.assertEqual(self.line.import_purchase_line_id, order.order_line)
        self.assertEqual(self.line.import_origin_state, "resolved")
        # and takes it back
        self._as(self._rows(fiscal_document_id=self.document.id), user).action_undo()
        self.assertEqual(self.line.import_origin_state, "pending")

    def test_a_buyer_without_the_fiscal_group_cannot_change_the_product(self):
        order = self._order()
        self.line.product_id = False
        rows = self._rows(fiscal_document_id=self.document.id)
        rows |= self._rows(purchase_line_id=order.order_line.id, kind="order")
        user = self._user("buyer-only-product", ("purchase.group_purchase_user",))

        with self.assertRaises(AccessError):
            self._as(rows, user).action_match()

        self.assertFalse(self.line.product_id)
        self.assertFalse(self.line.import_purchase_line_id)

    def test_the_fiscal_profile_chooses_the_product_of_the_order(self):
        order = self._order()
        self.line.product_id = False
        rows = self._rows(fiscal_document_id=self.document.id)
        rows |= self._rows(purchase_line_id=order.order_line.id, kind="order")
        user = self._user(
            "fiscal-buyer-product",
            ("l10n_br_fiscal.group_user", "purchase.group_purchase_user"),
        )

        self._as(rows, user).action_match()

        self.assertEqual(self.line.product_id, self.product)

    def test_the_screen_writes_only_the_fields_of_the_origin(self):
        rows = self._note_rows()

        with self.assertRaises(AccessError):
            rows._write_origin(self.line, {"product_id": False})
        with self.assertRaises(AccessError):
            rows._write_origin(self.line, {"price_unit": 1.0})

    def test_the_fiscal_profile_reads_the_orders_of_its_company_only(self):
        order = self._order()
        self.env.flush_all()
        fiscal = self._user("fiscal-reader", ("l10n_br_fiscal.group_user",))
        other = self._user(
            "fiscal-reader-other",
            ("l10n_br_fiscal.group_user",),
            companies=self.other_company,
        )

        rows = self._as(self.Match, fiscal).search([("kind", "=", "order")])
        other_rows = self._as(self.Match, other).search([("kind", "=", "order")])

        self.assertIn(order, rows.purchase_order_id)
        self.assertNotIn(order, other_rows.purchase_order_id)

    def test_a_row_of_another_company_is_not_reached_by_id(self):
        order = self._order()
        rows = self._note_rows()
        rows |= self._rows(purchase_line_id=order.order_line.id, kind="order")
        user = self._user(
            "other-company-id",
            ("l10n_br_fiscal.group_user", "purchase.group_purchase_user"),
            companies=self.other_company,
        )

        with self.assertRaises(AccessError):
            self._as(rows, user).action_match()

        self.assertNotEqual(self.line.import_origin_state, "resolved")
