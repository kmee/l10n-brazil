# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAccountMoveDefaultOperation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        # an operation whose lines lead to a single document type (service)
        cls.service_operation = cls.env.ref("l10n_br_fiscal.fo_venda").copy(
            {"name": "Test - Service Sale"}
        )
        service_line = cls.service_operation.line_ids.filtered(
            lambda line: line.document_type_id.code == "SE"
        )
        (cls.service_operation.line_ids - service_line).unlink()
        cls.service_document_type = service_line.document_type_id
        cls.env.company.sale_fiscal_operation_id = cls.service_operation

    def _new_invoice(self, **context):
        return Form(
            self.env["account.move"].with_context(
                default_move_type="out_invoice", **context
            )
        )

    def test_customer_invoice_suggests_the_operation_and_its_document_type(self):
        invoice = self._new_invoice()
        self.assertEqual(invoice.fiscal_operation_id, self.service_operation)
        self.assertEqual(invoice.document_type_id, self.service_document_type)

    def test_no_suggestion_when_the_operation_has_several_document_types(self):
        self.env.company.sale_fiscal_operation_id = self.env.ref(
            "l10n_br_fiscal.fo_venda"
        )
        invoice = self._new_invoice()
        self.assertFalse(invoice.fiscal_operation_id)
        self.assertFalse(invoice.document_type_id)

    def test_vendor_bill_does_not_take_the_sale_operation(self):
        bill = Form(
            self.env["account.move"].with_context(default_move_type="in_invoice")
        )
        self.assertFalse(bill.fiscal_operation_id)

    def test_an_operation_given_by_the_caller_is_kept(self):
        other = self.env.ref("l10n_br_fiscal.fo_devolucao_venda")
        invoice = self._new_invoice(default_fiscal_operation_id=other.id)
        self.assertEqual(invoice.fiscal_operation_id, other)
