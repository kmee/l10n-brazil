# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from datetime import date

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from .common_entrada import SpedEntradaCommon


@tagged("post_install", "-at_install")
class TestPreviousPeriods(SpedEntradaCommon):
    """A month with movement that was never assessed breaks the chain of the credit
    balance: the assessment says it, in the common point of every tax."""

    def _assess(self, month, post=True):
        group = self.env["account.tax.group"].search(
            [
                (
                    "fiscal_tax_group_id",
                    "=",
                    self.env.ref("l10n_br_fiscal.tax_group_icms").id,
                )
            ],
            limit=1,
        )
        if not group.with_company(self.company).property_tax_payable_account_id:
            accounts = {
                "property_tax_payable_account_id": ("ICMSPAY", "liability_current"),
                "property_tax_receivable_account_id": ("ICMSREC", "asset_current"),
            }
            group.with_company(self.company).write(
                {
                    field: self.env["account.account"]
                    .create(
                        {
                            "name": code,
                            "code": code,
                            "account_type": account_type,
                            "company_id": self.company.id,
                        }
                    )
                    .id
                    for field, (code, account_type) in accounts.items()
                }
            )
        assessment = self.env["l10n_br_tax.assessment"].create(
            {
                "company_id": self.company.id,
                "tax_group_id": group.id,
                "date_from": date(2026, month, 1),
                "date_to": date(2026, month, 28),
            }
        )
        assessment.action_compute()
        if post:
            assessment.action_post()
        return assessment

    def test_the_assessment_warns_of_an_earlier_month_with_movement(self):
        self._purchase_move(
            "fo_compras_compras_comercializacao", "601", invoice_date=date(2026, 6, 10)
        )
        self._purchase_move("fo_compras_compras_comercializacao", "602")
        july = self._assess(7, post=False)
        self.assertIn("06/2026", july.previous_periods_warning)
        with self.assertRaises(UserError) as error:
            july._check_previous_periods()
        self.assertIn("06/2026", error.exception.args[0])

    def test_there_is_no_warning_when_the_earlier_month_is_assessed_and_posted(self):
        self._purchase_move(
            "fo_compras_compras_comercializacao", "601", invoice_date=date(2026, 6, 10)
        )
        self._purchase_move("fo_compras_compras_comercializacao", "602")
        self._assess(6)
        july = self._assess(7, post=False)
        self.assertFalse(july.previous_periods_warning)
        july._check_previous_periods()

    def test_a_month_without_movement_does_not_have_to_be_assessed(self):
        self._purchase_move("fo_compras_compras_comercializacao", "602")
        july = self._assess(7, post=False)
        self.assertFalse(july.previous_periods_warning)
