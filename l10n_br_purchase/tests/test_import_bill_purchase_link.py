# Copyright 2026 KMEE - Luis Felipe Mileo <mileo@kmee.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestImportBillPurchaseLink(TransactionCase):
    """The vendor bill born from an imported fiscal document is linked to the
    purchase order lines the supplier referred to (xPed and nItemPed)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.po_products = cls.env.ref("l10n_br_purchase.lp_po_only_products")
        cls.fsc_op_purchase = cls.env.ref("l10n_br_fiscal.fo_compras")
        cls.fsc_op_line_purchase = cls.env.ref("l10n_br_fiscal.fo_compras_compras")

    def _confirmed_order(self):
        order = self.po_products
        for line in order.order_line:
            line.product_id.purchase_method = "purchase"
        order.button_confirm()
        return order

    def _import(self, order, references):
        """Import a document with one line per order line; ``references`` is
        a list of (xPed, nItemPed) for each of them."""
        document = (
            self.env["l10n_br_fiscal.document"]
            .with_company(order.company_id)
            .create(
                {
                    "company_id": order.company_id.id,
                    "fiscal_operation_id": self.fsc_op_purchase.id,
                    "fiscal_operation_type": "in",
                    "document_type_id": self.env.ref("l10n_br_fiscal.document_55").id,
                    "document_number": str(
                        len(self.env["l10n_br_fiscal.document"].search([]))
                    ),
                    "document_serie": "1",
                    "issuer": "partner",
                    "partner_id": order.partner_id.id,
                    "imported_document": True,
                }
            )
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
                    "fiscal_operation_id": self.fsc_op_purchase.id,
                    "fiscal_operation_line_id": self.fsc_op_line_purchase.id,
                    "fiscal_operation_type": "in",
                    "partner_order": xped,
                    "partner_order_line": nitemped,
                }
            )
        move_form = (
            self.env["account.move"]
            .with_company(order.company_id)
            .import_fiscal_document(document)
        )
        return self.env["account.move"].browse(move_form.id)

    def test_bill_lines_follow_the_supplier_reference(self):
        order = self._confirmed_order()
        count = len(order.order_line)
        move = self._import(order, [(order.name, str(n + 1)) for n in range(count)])
        self.assertEqual(move.invoice_line_ids.purchase_line_id, order.order_line)
        for line in order.order_line:
            self.assertEqual(line.qty_invoiced, line.product_qty)
        self.assertEqual(order.invoice_status, "invoiced")
        self.assertEqual(move.invoice_origin, order.name)

    def test_no_reference_stays_unlinked(self):
        order = self._confirmed_order()
        move = self._import(order, [(False, False)] * len(order.order_line))
        self.assertFalse(move.invoice_line_ids.purchase_line_id)
        self.assertFalse(move.invoice_origin)
        self.assertEqual(order.invoice_status, "to invoice")

    def test_unknown_order_or_item_stays_unlinked(self):
        order = self._confirmed_order()
        count = len(order.order_line)
        move = self._import(order, [("NOPE", "1")] * count)
        self.assertFalse(move.invoice_line_ids.purchase_line_id)
        move = self._import(order, [(order.name, "99")] * count)
        self.assertFalse(move.invoice_line_ids.purchase_line_id)

    def _import_split(self, order, quantities):
        """Import a document whose lines are the first order line split by
        lot: one document line for each quantity, all with the same xPed and
        nItemPed."""
        purchase_line = order.order_line[0]
        document = (
            self.env["l10n_br_fiscal.document"]
            .with_company(order.company_id)
            .create(
                {
                    "company_id": order.company_id.id,
                    "fiscal_operation_id": self.fsc_op_purchase.id,
                    "fiscal_operation_type": "in",
                    "document_type_id": self.env.ref("l10n_br_fiscal.document_55").id,
                    "document_number": str(
                        len(self.env["l10n_br_fiscal.document"].search([]))
                    ),
                    "document_serie": "1",
                    "issuer": "partner",
                    "partner_id": order.partner_id.id,
                    "imported_document": True,
                }
            )
        )
        for quantity in quantities:
            self.env["l10n_br_fiscal.document.line"].create(
                {
                    "document_id": document.id,
                    "name": purchase_line.name,
                    "product_id": purchase_line.product_id.id,
                    "quantity": quantity,
                    "price_unit": purchase_line.price_unit,
                    "fiscal_operation_id": self.fsc_op_purchase.id,
                    "fiscal_operation_line_id": self.fsc_op_line_purchase.id,
                    "fiscal_operation_type": "in",
                    "partner_order": order.name,
                    "partner_order_line": "1",
                }
            )
        move_form = (
            self.env["account.move"]
            .with_company(order.company_id)
            .import_fiscal_document(document)
        )
        return self.env["account.move"].browse(move_form.id)

    def test_an_order_line_takes_the_lines_the_supplier_split(self):
        """The supplier splits the same item by lot (common for medicines): the
        order line takes every line of the bill while the sum stays within it,
        and counts all of them as invoiced."""
        order = self._confirmed_order()
        purchase_line = order.order_line[0]
        quantity = purchase_line.product_qty
        move = self._import_split(order, [quantity / 2, quantity / 2])
        self.assertEqual(len(move.invoice_line_ids), 2)
        self.assertEqual(move.invoice_line_ids.purchase_line_id, purchase_line)
        self.assertEqual(
            len(move.invoice_line_ids.filtered("purchase_line_id")),
            2,
            "both lines are linked to the order line",
        )
        self.assertEqual(purchase_line.qty_invoiced, quantity)

    def test_what_passes_the_balance_of_the_order_line_is_not_linked(self):
        order = self._confirmed_order()
        purchase_line = order.order_line[0]
        quantity = purchase_line.product_qty
        move = self._import_split(order, [quantity * 0.75, quantity * 0.75])
        linked = move.invoice_line_ids.filtered("purchase_line_id")
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked.quantity, quantity * 0.75)
        self.assertEqual(purchase_line.qty_invoiced, quantity * 0.75)

    def test_the_tolerance_of_the_quantity_widens_the_balance(self):
        order = self._confirmed_order()
        if "purchase_quantity_tolerance" not in order.company_id._fields:
            self.skipTest("the quantity tolerance belongs to l10n_br_purchase_stock")
        quantity = order.order_line[0].product_qty
        order.company_id.purchase_quantity_tolerance = 20.0
        move = self._import_split(order, [quantity * 0.7, quantity * 0.5])
        self.assertEqual(
            len(move.invoice_line_ids.filtered("purchase_line_id")),
            2,
            "1.2 of the ordered quantity is within the tolerance of 20%",
        )
        order.company_id.purchase_quantity_tolerance = 10.0
        move.invoice_line_ids.write({"purchase_line_id": False})
        move._link_purchase_lines_from_fiscal_reference()
        self.assertEqual(
            len(move.invoice_line_ids.filtered("purchase_line_id")),
            1,
            "1.2 is not within a tolerance of 10%",
        )
