# Copyright 2025 - Engenere (<https://engenere.one>).
# @author Antônio S. Pereira Neto <neto@engenere.one>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields
from odoo.tests import Form, tagged

from odoo.addons.mail.tests.common import MailCommon

from .common import AccountMoveBRCommon


@tagged("post_install", "-at_install")
class TestPaymentStatusBR(AccountMoveBRCommon, MailCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Enable tracking (needed by this scenario)
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=False))
        cls.configure_normal_company_taxes()

    def test_payment_status_partial_paid_partial(self):
        invoice = self.init_invoice(
            "out_invoice",
            products=[self.product_a],
            document_type=self.env.ref("l10n_br_fiscal.document_55"),
            document_serie_id=self.empresa_lc_document_55_serie_1,
            fiscal_operation=self.env.ref("l10n_br_fiscal.fo_venda"),
            fiscal_operation_lines=[self.env.ref("l10n_br_fiscal.fo_venda_venda")],
        )
        invoice.action_post()
        self.assertEqual(invoice.payment_state, "not_paid")
        self.assertEqual(invoice.amount_residual, 1032.5)

        # First partial payment
        self._register_payment(invoice, 600.0)
        self.assertEqual(invoice.payment_state, "partial")

        # Second partial payment (completes amount)
        pmt2 = self._register_payment(invoice, 432.5)
        self.assertEqual(invoice.payment_state, "paid")
        self.assertEqual(invoice.amount_residual, 0.0)
        self.flush_tracking()

        # Remove pmt2 partial reconciliation and assert effects
        def _is_receivable(line):
            return line.account_id.account_type == "asset_receivable"

        inv_recv = invoice.line_ids.filtered(_is_receivable)
        pay_recv = pmt2.move_id.line_ids.filtered(_is_receivable)
        partial_to_remove = inv_recv.matched_credit_ids & pay_recv.matched_debit_ids
        invoice.js_remove_outstanding_partial(partial_to_remove.id)

        self.assertEqual(invoice.amount_residual, 432.5)
        self.assertEqual(invoice.payment_state, "partial")

    def test_early_payment_discount_term(self):
        """Fatura com condicao de pagamento com desconto antecipado de 2%."""
        term = self.env["account.payment.term"].create(
            {
                "name": "2% ate 10 dias",
                "early_discount": True,
                "discount_percentage": 2.0,
                "discount_days": 10,
                "line_ids": [
                    (0, 0, {"value": "percent", "value_amount": 100.0, "nb_days": 30})
                ],
            }
        )
        invoice = self.init_invoice(
            "out_invoice",
            products=[self.product_a],
            document_type=self.env.ref("l10n_br_fiscal.document_55"),
            document_serie_id=self.empresa_lc_document_55_serie_1,
            fiscal_operation=self.env.ref("l10n_br_fiscal.fo_venda"),
            fiscal_operation_lines=[self.env.ref("l10n_br_fiscal.fo_venda_venda")],
        )
        invoice.invoice_payment_term_id = term
        invoice.action_post()
        expected = invoice.currency_id.round(invoice.amount_total * 0.98)
        term_line = invoice.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )
        self.assertEqual(len(term_line), 1)
        self.assertEqual(term_line.discount_amount_currency, expected)
        self.assertEqual(term_line.discount_balance, expected)
        # O assistente de pagamento, dentro do prazo, propoe o valor com desconto.
        wiz = (
            self.env["account.payment.register"]
            .with_context(active_model="account.move", active_ids=invoice.ids)
            .create({"payment_date": invoice.invoice_date})
        )
        self.assertEqual(wiz.amount, expected)

    def _register_payment(self, invoice, amount):
        bank_journal = self.company_data["default_journal_bank"]
        with Form(
            self.env["account.payment.register"].with_context(
                active_model="account.move", active_ids=invoice.ids
            )
        ) as wiz_form:
            wiz_form.journal_id = bank_journal
            wiz_form.payment_date = fields.Date.today()
            wiz_form.amount = amount
        wiz = wiz_form.save()
        payments = wiz._create_payments()
        return payments
