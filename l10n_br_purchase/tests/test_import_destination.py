# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_br_fiscal.constants.fiscal import TAX_FRAMEWORK_NORMAL


@tagged("post_install", "-at_install")
class TestImportDestination(TransactionCase):
    """The destination of the order follows into the imported document line.

    The supplier note carries an outgoing CFOP (6102), whose inverse suggests
    the default operation line of the company: it cannot know the order was
    placed for use and consumption. When the origin of the line is decided,
    the line takes the operation line (and so the destination) of the order,
    and the vendor bill books no ICMS credit for it.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        ref = cls.env.ref
        cls.order = ref("l10n_br_purchase.lp_po_only_products")
        cls.order.partner_id.tax_framework = TAX_FRAMEWORK_NORMAL
        cls.operation = ref("l10n_br_fiscal.fo_compras")
        cls.consumption = ref("l10n_br_fiscal.fo_compras_compras_uso_consumo")
        cls.asset = ref("l10n_br_fiscal.fo_compras_compras_ativo")
        ref("l10n_br_fiscal.cfop_6102").cfop_inverse_id = ref(
            "l10n_br_fiscal.cfop_2102"
        )
        for line in cls.order.order_line:
            line.product_id.purchase_method = "purchase"
        cls.order.order_line.write({"fiscal_operation_line_id": cls.consumption.id})
        cls.order.button_confirm()

    def _document(self, suggest=True, **line_vals):
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
        ref = self.env.ref
        for order_line in order.order_line:
            base = order_line.product_qty * order_line.price_unit
            self.env["l10n_br_fiscal.document.line"].create(
                {
                    "document_id": document.id,
                    "name": order_line.name,
                    "product_id": order_line.product_id.id,
                    "quantity": order_line.product_qty,
                    "price_unit": order_line.price_unit,
                    "fiscal_operation_id": self.operation.id,
                    "fiscal_operation_type": "in",
                    "partner_cfop_id": ref("l10n_br_fiscal.cfop_6102").id,
                    "icms_origin": "0",
                    "icms_tax_id": ref("l10n_br_fiscal.tax_icms_12").id,
                    "icms_cst_id": ref("l10n_br_fiscal.cst_icms_00").id,
                    "icms_base": base,
                    "icms_percent": 12.0,
                    "icms_value": base * 0.12,
                    "partner_order": order.name,
                    "partner_order_line": "1",
                    **line_vals,
                }
            )
        if suggest:
            document._init_import_states()
        return document

    def _bill(self, document):
        move_form = (
            self.env["account.move"]
            .with_company(self.order.company_id)
            .import_fiscal_document(document)
        )
        return self.env["account.move"].browse(move_form.id)

    @staticmethod
    def _icms_lines(move):
        return move.line_ids.filtered(
            lambda line: line.tax_line_id.tax_group_id.fiscal_tax_group_id.tax_domain
            == "icms"
        )

    def test_confirming_the_origin_brings_the_destination_of_the_order(self):
        document = self._document()
        default = document.fiscal_line_ids.fiscal_operation_line_id
        self.assertNotIn(self.consumption, default, "the default is not the order")
        control = self._bill(
            self._document(suggest=False, partner_order=False, partner_order_line=False)
        )
        self.assertTrue(
            self._icms_lines(control), "the default destination takes the credit"
        )

        self.assertEqual(
            set(document.fiscal_line_ids.mapped("import_origin_state")), {"suggested"}
        )
        document.action_confirm_import_origins()
        for line in document.fiscal_line_ids:
            self.assertEqual(line.fiscal_operation_line_id, self.consumption)
            self.assertEqual(line.product_destination, "use_consumption")
        bill = self._bill(document)
        self.assertEqual(bill.invoice_line_ids.purchase_line_id, self.order.order_line)
        self.assertFalse(self._icms_lines(bill), "no ICMS credit for consumption")
        self.assertAlmostEqual(sum(bill.line_ids.mapped("balance")), 0.0)

    def test_choosing_the_order_line_brings_the_destination_too(self):
        document = self._document(partner_order=False, partner_order_line=False)
        for fiscal_line, order_line in zip(
            document.fiscal_line_ids, self.order.order_line, strict=True
        ):
            fiscal_line.import_purchase_line_id = order_line
            self.assertEqual(fiscal_line.fiscal_operation_line_id, self.consumption)

    def test_the_choice_of_the_person_on_the_line_is_kept(self):
        document = self._document()
        document.fiscal_line_ids.fiscal_operation_line_id = self.asset
        document.action_confirm_import_origins()
        for line in document.fiscal_line_ids:
            self.assertEqual(line.fiscal_operation_line_id, self.asset)

    def test_the_bill_of_a_suggested_origin_shows_the_warning(self):
        """The destination is applied only to a confirmed origin, so the bill
        generated while the origin is only suggested warns about it."""
        document = self._document()
        self.assertEqual(
            set(document.fiscal_line_ids.mapped("import_origin_state")), {"suggested"}
        )
        bill = self._bill(document)
        self.assertTrue(bill.has_unconfirmed_import_origin)
        view = bill.get_view(self.env.ref("account.view_move_form").id, "form")
        self.assertIn("has_unconfirmed_import_origin", view["arch"])
        document.action_confirm_import_origins()
        bill.invalidate_recordset(["has_unconfirmed_import_origin"])
        self.assertFalse(bill.has_unconfirmed_import_origin)

    def test_a_bill_without_pending_origin_has_no_warning(self):
        document = self._document(
            suggest=False, partner_order=False, partner_order_line=False
        )
        bill = self._bill(document)
        self.assertFalse(bill.has_unconfirmed_import_origin)
