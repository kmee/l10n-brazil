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
                    "document_number": "1001",
                    "document_serie": "1",
                    "issuer": "partner",
                    "partner_id": order.partner_id.id,
                    "imported_document": True,
                }
            )
        )
        for purchase_line, (xped, nitemped) in zip(order.order_line, references):
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
