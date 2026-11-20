# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import Form, tagged

from .common import AccountMoveBRCommon


@tagged("post_install", "-at_install")
class TestPaymentTermOnSavedDraft(AccountMoveBRCommon):
    def _draft_without_operation_line(self):
        self.configure_normal_company_taxes()
        form = Form(
            self.env["account.move"].with_context(default_move_type="out_invoice")
        )
        form.partner_id = self.partner_a
        form.document_type_id = self.env.ref("l10n_br_fiscal.document_55")
        form.document_serie_id = self.empresa_lc_document_55_serie_1
        form.fiscal_operation_id = self.env.ref("l10n_br_fiscal.fo_venda")
        form.invoice_payment_term_id = self.env["account.payment.term"]
        with form.invoice_line_ids.new() as line:
            line.product_id = self.product_a
            line.quantity = 2
            line.price_unit = 50.0
        move = form.save()
        # no operation line of the operation matches the line
        move.invoice_line_ids.write(
            {"fiscal_operation_line_id": False, "cfop_id": False}
        )
        self.env.flush_all()
        self.env.invalidate_all()
        return move

    def _terms(self):
        term = self.env["account.payment.term"]
        return [
            term.create(
                {
                    "name": "30% now, balance in 60 days",
                    "line_ids": [
                        Command.create(
                            {"value": "percent", "value_amount": 30, "days": 0}
                        ),
                        Command.create({"value": "balance", "days": 60}),
                    ],
                }
            ),
            term.create(
                {
                    "name": "30/60/90",
                    "line_ids": [
                        Command.create(
                            {"value": "percent", "value_amount": 33, "days": 30}
                        ),
                        Command.create(
                            {"value": "percent", "value_amount": 33, "days": 60}
                        ),
                        Command.create({"value": "balance", "days": 90}),
                    ],
                }
            ),
        ]

    def test_payment_term_chosen_on_a_saved_draft_without_operation_line(self):
        move = self._draft_without_operation_line()
        for term in self._terms():
            with Form(move) as form:
                form.invoice_payment_term_id = term
            due = move.line_ids.filtered(
                lambda line: line.account_id.account_type == "asset_receivable"
            )
            self.assertEqual(len(due), len(term.line_ids), term.name)
            self.assertAlmostEqual(sum(due.mapped("debit")), 100.0, places=2)
            self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0, places=2)
