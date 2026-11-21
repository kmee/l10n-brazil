# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestAccountMoveDefaultOperation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.operation = cls.env.ref("l10n_br_fiscal.fo_venda")
        cls.env.company.sale_fiscal_operation_id = cls.operation

    def test_customer_invoice_suggests_the_sale_operation_of_the_company(self):
        invoice = Form(
            self.env["account.move"].with_context(default_move_type="out_invoice")
        )
        self.assertEqual(invoice.fiscal_operation_id, self.operation)

    def test_vendor_bill_does_not_take_the_sale_operation(self):
        bill = Form(
            self.env["account.move"].with_context(default_move_type="in_invoice")
        )
        self.assertNotEqual(bill.fiscal_operation_id, self.operation)

    def test_an_operation_given_by_the_caller_is_kept(self):
        other = self.env.ref("l10n_br_fiscal.fo_devolucao_venda")
        invoice = Form(
            self.env["account.move"].with_context(
                default_move_type="out_invoice", default_fiscal_operation_id=other.id
            )
        )
        self.assertEqual(invoice.fiscal_operation_id, other)
