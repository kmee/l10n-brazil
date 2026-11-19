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

    def test_a_balance_claimed_by_another_imported_document_is_not_offered(self):
        """Two notes imported and still without a bill cannot both claim the
        same balance of the order: what the first one took is not offered to
        the second."""
        count = len(self.order.order_line)
        first = self._document([(False, False)] * count)
        first._init_import_states()
        taken = first.fiscal_line_ids.mapped("import_purchase_line_id")
        self.assertTrue(taken)
        second = self._document([(False, False)] * count)
        second._init_import_states()
        for line in second.fiscal_line_ids.filtered(
            lambda line: line.product_id in taken.mapped("product_id")
        ):
            self.assertFalse(line.import_purchase_line_id)
            self.assertFalse(line.import_origin_candidate_ids)
        # the first note gives it up: the balance is free again
        first.fiscal_line_ids.write({"import_purchase_line_id": False})
        second.fiscal_line_ids._suggest_import_origin()
        self.assertEqual(
            second.fiscal_line_ids.mapped("import_purchase_line_id"), taken
        )

    def test_the_candidates_of_a_big_document_are_read_once(self):
        """The candidates are read for all the lines together: the number of
        queries does not grow with the number of lines."""

        def candidates_queries(document):
            lines = document.fiscal_line_ids
            lines.invalidate_recordset(["import_origin_candidate_ids"])
            self.env.flush_all()
            before = self.env.cr.sql_log_count
            lines.mapped("import_origin_candidate_ids")
            return self.env.cr.sql_log_count - before

        small = self._document([(False, False)] * len(self.order.order_line))
        small_queries = candidates_queries(small)
        big = self._document([(False, False)] * len(self.order.order_line))
        # many more lines for the same supplier
        template = big.fiscal_line_ids[0]
        for _n in range(20):
            template.copy({"document_id": big.id})
        self.assertGreater(len(big.fiscal_line_ids), len(small.fiscal_line_ids) + 15)
        self.assertLessEqual(candidates_queries(big), small_queries + 3)

    def _one_line_document(self, order_line):
        """An imported document with one line that takes the whole order line."""
        document = self._document([(False, False)] * len(self.order.order_line))
        extra = document.fiscal_line_ids.filtered(
            lambda line: line.product_id != order_line.product_id
        )
        extra.unlink()
        line = document.fiscal_line_ids
        line.quantity = order_line.product_qty
        return document

    def test_four_notes_never_claim_the_same_balance_whatever_the_way_they_enter(self):
        """Four notes for the whole order line: only the first one gets it, in
        separate runs (cold cache between them) and in the same batch (the zip),
        always the same result."""
        order_line = self.order.order_line[0]
        # separate runs: a cold cache before each note
        documents = []
        for _n in range(4):
            self.env.invalidate_all()
            document = self._one_line_document(order_line)
            document._init_import_states()
            documents.append(document)
        suggested = [bool(d.fiscal_line_ids.import_purchase_line_id) for d in documents]
        self.assertEqual(suggested, [True, False, False, False])

        # the same batch: the notes exist before the suggestion, which runs once
        for document in documents:
            document.fiscal_line_ids.write({"import_purchase_line_id": False})
        batch = self.env["l10n_br_fiscal.document.line"]
        for document in documents:
            batch |= document.fiscal_line_ids
        batch._suggest_import_origin()
        suggested = [bool(d.fiscal_line_ids.import_purchase_line_id) for d in documents]
        self.assertEqual(suggested, [True, False, False, False])
