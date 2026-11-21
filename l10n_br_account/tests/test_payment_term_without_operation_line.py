# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests.common import Form, TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestPaymentTermWithoutOperationLine(TransactionCase):
    """A customer invoice saved with a line that no operation line matches keeps
    its receivable when the payment term is chosen afterwards."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.env.user.company_ids |= cls.company
        cls.env.user.company_id = cls.company
        cls.env.user.groups_id += cls.env.ref("l10n_br_fiscal.group_user")
        cls.term = cls.env.ref("account.account_payment_term_30days")

    def _draft_invoice(self):
        operation = self.env.ref("l10n_br_fiscal.fo_venda")
        return self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "company_id": self.company.id,
                "partner_id": self.env.ref("l10n_br_base.res_partner_cliente1_sp").id,
                "document_type_id": self.env.ref("l10n_br_fiscal.document_55").id,
                "document_serie_id": self.env.ref(
                    "l10n_br_fiscal.empresa_lc_document_55_serie_1"
                ).id,
                "fiscal_operation_id": operation.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": self.env.ref("product.product_product_7").id,
                            "quantity": 2,
                            "price_unit": 50,
                            "fiscal_operation_id": operation.id,
                            "fiscal_operation_line_id": self.env.ref(
                                "l10n_br_fiscal.fo_venda_venda"
                            ).id,
                        }
                    )
                ],
            }
        )

    def test_term_chosen_on_a_saved_draft_without_operation_line(self):
        move = self._draft_invoice()
        move.invoice_line_ids.fiscal_operation_line_id = False
        self.assertFalse(move.invoice_line_ids.fiscal_operation_line_id)
        self.env.flush_all()
        self.env.invalidate_all()

        with Form(move) as form:
            form.invoice_payment_term_id = self.term

        receivable = move.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        self.assertEqual(sum(receivable.mapped("debit")), move.amount_total)
        self.assertEqual(move.amount_total, 100)
        self.assertEqual(len(receivable), 1)
