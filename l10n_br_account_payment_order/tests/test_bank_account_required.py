# Copyright (C) 2026 - KMEE (<http://kmee.com.br>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestBankAccountRequired(AccountTestInvoicingCommon):
    @classmethod
    def setUpClass(cls):
        cls.chart_template = "br_oca_generic"
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.company_data["company"]
        cls.method = cls.env.ref(
            "l10n_br_account_payment_order.payment_mode_type_cnab240_out"
        )
        cls.bank = cls.env.ref("l10n_br_base.res_bank_341")

    def _line(self, domain, **vals):
        mode = self.env["account.payment.mode"].create(
            {
                "bank_account_link": "variable",
                "name": domain,
                "company_id": self.company.id,
                "payment_method_id": self.method.id,
                "payment_mode_domain": domain,
                "payment_order_ok": True,
                "variable_journal_ids": self.company_data["default_journal_bank"],
            }
        )
        order = self.env["account.payment.order"].create(
            {
                "payment_mode_id": mode.id,
                "journal_id": self.company_data["default_journal_bank"].id,
            }
        )
        values = {
            "order_id": order.id,
            "partner_id": self.partner_a.id,
            "amount_currency": 1234.56,
            "communication_type": "normal",
            "communication": "TED TEST",
        }
        values.update(vals)
        return self.env["account.payment.line"].create(values)

    def _bank_account(self, **vals):
        values = {
            "bank_id": self.bank.id,
            "partner_id": self.partner_a.id,
            "acc_number": "123456",
            "bra_number": "0001",
        }
        values.update(vals)
        return self.env["res.partner.bank"].create(values)

    def test_ted_and_doc_without_bank_account_block(self):
        for domain in ("ted", "doc"):
            line = self._line(domain)
            with self.assertRaises(UserError) as ctx:
                line.draft2open_payment_line_check()
            message = str(ctx.exception)
            self.assertIn(line.name, message)
            self.assertIn(self.partner_a.display_name, message)
            self.assertRegex(message, r"1[.,]234[.,]56")

    def test_ted_with_incomplete_bank_account_blocks(self):
        for field in ("acc_number", "bra_number"):
            line = self._line(
                "ted", partner_bank_id=self._bank_account(**{field: ""}).id
            )
            with self.assertRaises(UserError):
                line.draft2open_payment_line_check()

    def test_ted_with_complete_bank_account_passes(self):
        line = self._line("ted", partner_bank_id=self._bank_account().id)
        line._check_bank_account_required()

    def test_boleto_and_dinheiro_are_not_checked(self):
        for domain in ("boleto", "dinheiro"):
            self._line(domain)._check_bank_account_required()
