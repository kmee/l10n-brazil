# Copyright 2026 KMEE - Luis Felipe Mileo <mileo@kmee.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestImportOrigin(TransactionCase):
    """The origin (purchase order line) of an imported document line lives on
    the persisted line, is suggested and then decided by a person."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.order = cls.env.ref("l10n_br_purchase.lp_po_only_products")
        cls.operation = cls.env.ref("l10n_br_fiscal.fo_compras")
        cls.operation_line = cls.env.ref("l10n_br_fiscal.fo_compras_compras")
        for line in cls.order.order_line:
            line.product_id.purchase_method = "purchase"
        cls.order.button_confirm()

    def _document(self, references):
        order = self.order
        document = self.env["l10n_br_fiscal.document"].create(
            {
                "company_id": order.company_id.id,
                "fiscal_operation_id": self.operation.id,
                "fiscal_operation_type": "in",
                "document_type_id": self.env.ref("l10n_br_fiscal.document_55").id,
                "document_number": str(
                    self.env["l10n_br_fiscal.document"].search_count([])
                ),
                "document_serie": "1",
                "issuer": "partner",
                "partner_id": order.partner_id.id,
                "imported_document": True,
            }
        )
        for purchase_line, (xped, nitemped) in zip(
            order.order_line, references, strict=True
        ):
            self.env["l10n_br_fiscal.document.line"].create(
                {
                    "document_id": document.id,
                    "name": purchase_line.name,
                    "product_id": purchase_line.product_id.id,
                    "quantity": purchase_line.product_qty,
                    "price_unit": purchase_line.price_unit,
                    "fiscal_operation_id": self.operation.id,
                    "fiscal_operation_line_id": self.operation_line.id,
                    "fiscal_operation_type": "in",
                    "partner_order": xped,
                    "partner_order_line": nitemped,
                }
            )
        return document

    def test_the_reference_of_the_file_is_resolved(self):
        """The supplier declared the order and the item and exactly one open
        line has the product: there is nothing left to decide."""
        count = len(self.order.order_line)
        document = self._document([(self.order.name, str(n + 1)) for n in range(count)])
        document._init_import_states()
        self.assertEqual(
            document.fiscal_line_ids.mapped("import_purchase_line_id"),
            self.order.order_line,
        )
        self.assertEqual(
            set(document.fiscal_line_ids.mapped("import_origin_state")), {"resolved"}
        )

    def test_the_only_open_line_of_the_product_is_just_suggested(self):
        """Without a reference of the file the only open line of the supplier
        for the product is a guess, and a person confirms it."""
        order = self.order
        for line in order.order_line:
            repeated = order.order_line.filtered(
                lambda other, line=line: other.product_id == line.product_id
            )
            if len(repeated) > 1:
                self.skipTest("the demo order repeats a product")
        document = self._document([(False, False)] * len(order.order_line))
        document._init_import_states()
        self.assertEqual(
            document.fiscal_line_ids.mapped("import_purchase_line_id"),
            order.order_line,
        )
        self.assertEqual(
            set(document.fiscal_line_ids.mapped("import_origin_state")), {"suggested"}
        )

    def test_several_candidates_without_reference_stay_pending(self):
        self.order.copy().button_confirm()
        document = self._document([(False, False)] * len(self.order.order_line))
        document._init_import_states()
        self.assertFalse(document.fiscal_line_ids.mapped("import_purchase_line_id"))
        self.assertEqual(
            set(document.fiscal_line_ids.mapped("import_origin_state")), {"pending"}
        )

    def test_the_person_decides_and_the_bill_follows_the_line(self):
        self.order.copy().button_confirm()
        document = self._document([(False, False)] * len(self.order.order_line))
        document._init_import_states()
        for fiscal_line, order_line in zip(
            document.fiscal_line_ids, self.order.order_line, strict=True
        ):
            fiscal_line.import_purchase_line_id = order_line
        self.assertEqual(
            set(document.fiscal_line_ids.mapped("import_origin_state")), {"resolved"}
        )
        # the bill takes reviewed lines only
        document.fiscal_line_ids.action_resolve_line()
        move_form = (
            self.env["account.move"]
            .with_company(self.order.company_id)
            .import_fiscal_document(document)
        )
        move = self.env["account.move"].browse(move_form.id)
        self.assertEqual(move.invoice_line_ids.purchase_line_id, self.order.order_line)
        self.assertEqual(move.invoice_origin, self.order.name)

    def test_confirming_the_suggestions(self):
        document = self._document([(False, False)] * len(self.order.order_line))
        document._init_import_states()
        self.assertTrue(document.has_suggested_import_origin)
        document.action_confirm_import_origins()
        self.assertFalse(document.has_suggested_import_origin)
        self.assertEqual(
            set(document.fiscal_line_ids.mapped("import_origin_state")), {"resolved"}
        )

    def test_the_order_line_is_shown_with_its_order(self):
        first, second = self.order.order_line[:2]
        names = dict(self.order.order_line.name_get())
        self.assertTrue(names[first.id].startswith(self.order.name + ": "))
        self.assertTrue(names[second.id].startswith(self.order.name + ": "))
        # and it is found by the number of the order
        found = self.env["purchase.order.line"].name_search(self.order.name)
        self.assertEqual(
            {line_id for line_id, _name in found}, set(self.order.order_line.ids)
        )

    def test_the_domain_of_the_field_is_the_candidates_of_the_suggestion(self):
        document = self._document([(False, False)] * len(self.order.order_line))
        line = document.fiscal_line_ids[0]
        expected = self.order.order_line.filtered(
            lambda order_line: order_line.product_id == line.product_id
        )
        self.assertEqual(line.import_origin_candidate_ids, expected)
        self.assertEqual(line._import_origin_candidates(), expected)
        # a draft order and the order of another supplier are not candidates
        self.order.copy()
        other = self.env["res.partner"].create({"name": "Other supplier"})
        self.order.copy({"partner_id": other.id}).button_confirm()
        line.invalidate_recordset(["import_origin_candidate_ids"])
        self.assertEqual(line.import_origin_candidate_ids, expected)
        # the field offers the candidates and the line already chosen
        domain = line._fields["import_purchase_line_id"].domain
        self.assertIn("import_origin_candidate_ids", domain)

    def test_an_origin_not_confirmed_blocks_the_bill(self):
        """An origin only suggested, or still pending, is not a decision: the
        bill is refused and the message says what to do."""
        count = len(self.order.order_line)
        document = self._document([(self.order.name, str(n + 1)) for n in range(count)])
        document._init_import_states()
        document.fiscal_line_ids.action_resolve_line()
        line = document.fiscal_line_ids[0]
        for state in ("suggested", "pending"):
            line.with_context(import_origin_suggestion=True).write(
                {"import_origin_state": state}
            )
            with self.assertRaisesRegex(UserError, "Confirm Origins"):
                document._check_document_import()
            with self.assertRaisesRegex(UserError, "Confirm Origins"):
                self.env["account.move"].import_fiscal_document(document)
            with self.assertRaisesRegex(UserError, "Confirm Origins"):
                document.action_document_confirm()
        document.action_confirm_import_origins()
        line.import_origin_state = "resolved"
        document._check_document_import()  # must not raise

    def test_the_bill_links_only_the_origin_that_was_decided(self):
        """A suggestion is not linked to the order: the order only counts what
        was decided (or what the supplier declared with no doubt)."""
        count = len(self.order.order_line)
        document = self._document([(self.order.name, str(n + 1)) for n in range(count)])
        document._init_import_states()
        document.fiscal_line_ids.action_resolve_line()
        move_form = (
            self.env["account.move"]
            .with_company(self.order.company_id)
            .import_fiscal_document(document)
        )
        move = self.env["account.move"].browse(move_form.id)
        move.invoice_line_ids.purchase_line_id = False
        document.fiscal_line_ids.with_context(import_origin_suggestion=True).write(
            {"import_origin_state": "suggested"}
        )
        move._link_purchase_lines_from_fiscal_reference()
        self.assertFalse(move.invoice_line_ids.purchase_line_id)
        document.action_confirm_import_origins()
        move._link_purchase_lines_from_fiscal_reference()
        self.assertEqual(move.invoice_line_ids.purchase_line_id, self.order.order_line)

    def test_a_pending_origin_with_nothing_to_choose_does_not_block(self):
        """A line whose product has no open order line only is pending because
        the supplier has other open orders: there is nothing to decide, so it
        does not hold the bill."""
        product = self.env["product.product"].create(
            {"name": "Product without order", "purchase_ok": True}
        )
        document = self._document([(False, False)] * len(self.order.order_line))
        document.fiscal_line_ids[1:].unlink()
        line = document.fiscal_line_ids
        line.product_id = product
        line.uom_id = product.uom_id
        document._init_import_states()
        self.assertEqual(line.import_origin_state, "pending")
        self.assertFalse(line.import_origin_candidate_ids)
        line.action_resolve_line()
        document._check_document_import()  # must not raise
