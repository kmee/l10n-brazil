# Copyright 2026 KMEE (Ygor Carvalho <ygor.carvalho@kmee.com.br>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from datetime import date, timedelta
from unittest.mock import patch

from odoo.tests.common import Form, tagged

from .common import AccountMoveBRCommon


@tagged("post_install", "-at_install")
class TestImportedDueDate(AccountMoveBRCommon):
    chart_template = "generic_coa"

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["account.chart.template"].load_fiscal_taxes(
            companies=[cls.company_data["company"]]
        )
        cls.configure_normal_company_taxes()

        cls.move = cls.init_invoice(
            "in_invoice",
            products=[cls.product_a],
            document_type=cls.env.ref("l10n_br_fiscal.document_55"),
            fiscal_operation=cls.env.ref("l10n_br_fiscal.fo_compras"),
            fiscal_operation_lines=[
                cls.env.ref("l10n_br_fiscal.fo_compras_compras_comercializacao")
            ],
            document_serie="1",
            document_number="4952",
        )
        cls.move.fiscal_document_id.sudo().imported_document = True

    def _terms_with(self, installments):
        document = self.move.fiscal_document_id
        with patch.object(
            type(document),
            "_get_imported_installments",
            lambda doc: installments,
        ):
            self.move._compute_needed_terms()
        return self.move.needed_terms

    def test_the_due_dates_come_from_the_file(self):
        """Without this the imported bill is due on the day it was imported."""
        terms = self._terms_with(
            [(date(2026, 9, 4), 300.0), (date(2026, 10, 4), 700.0)]
        )

        self.assertEqual(
            sorted(key["date_maturity"] for key in terms),
            [date(2026, 9, 4), date(2026, 10, 4)],
        )

    def test_the_installments_add_up_to_the_document_total(self):
        """The move has to balance even when the file does not add up.

        The weights come from the file, the total comes from the document, so
        the terms always close on amount_total_signed.
        """
        terms = self._terms_with([(date(2026, 9, 4), 1.0), (date(2026, 10, 4), 2.0)])

        self.assertAlmostEqual(
            sum(values["balance"] for values in terms.values()),
            self.move.amount_total_signed,
            places=2,
        )
        by_date = {key["date_maturity"]: values for key, values in terms.items()}
        one_third = self.move.amount_total_signed / 3
        self.assertAlmostEqual(
            by_date[date(2026, 9, 4)]["balance"], one_third, places=2
        )

    def test_installments_on_the_same_date_are_merged(self):
        terms = self._terms_with([(date(2026, 9, 4), 400.0), (date(2026, 9, 4), 600.0)])

        self.assertEqual(len(terms), 1)
        self.assertAlmostEqual(
            next(iter(terms.values()))["balance"],
            self.move.amount_total_signed,
            places=2,
        )

    def test_a_file_without_installments_keeps_the_single_term(self):
        terms = self._terms_with([])

        self.assertEqual(len(terms), 1)
        self.assertEqual(
            next(iter(terms))["date_maturity"],
            self.move.invoice_date_due,
        )

    def _split_term(self):
        return self.env["account.payment.term"].create(
            {
                "name": "70% 18 days / 30% 48 days",
                "line_ids": [
                    (
                        0,
                        0,
                        {
                            "value": "percent",
                            "value_amount": 70.0,
                            "delay_type": "days_after",
                            "nb_days": 18,
                        },
                    ),
                    (
                        0,
                        0,
                        {
                            "value": "percent",
                            "value_amount": 30.0,
                            "delay_type": "days_after",
                            "nb_days": 48,
                        },
                    ),
                ],
            }
        )

    def test_the_payment_term_splits_a_file_without_installments(self):
        """The term the user chose is not ignored on an imported bill."""
        self.move.invoice_payment_term_id = self._split_term()
        terms = self._terms_with([])

        invoice_date = self.move.invoice_date or self.move.date
        by_date = {key["date_maturity"]: values for key, values in terms.items()}
        self.assertEqual(
            sorted(by_date),
            [invoice_date + timedelta(days=18), invoice_date + timedelta(days=48)],
        )
        # Whatever the split, it has to close on what the move balances against.
        self.assertAlmostEqual(
            sum(values["balance"] for values in terms.values()),
            self.move.amount_total_signed,
            places=2,
        )
        self.assertAlmostEqual(
            by_date[invoice_date + timedelta(days=18)]["balance"],
            self.move.amount_total_signed * 0.7,
            places=2,
        )

    def test_the_installments_of_the_file_win_over_the_payment_term(self):
        self.move.invoice_payment_term_id = self._split_term()
        terms = self._terms_with(
            [(date(2026, 9, 4), 300.0), (date(2026, 10, 4), 700.0)]
        )

        self.assertEqual(
            sorted(key["date_maturity"] for key in terms),
            [date(2026, 9, 4), date(2026, 10, 4)],
        )

    def test_no_installments_and_no_payment_term_keeps_the_single_term(self):
        self.move.invoice_payment_term_id = False
        terms = self._terms_with([])

        self.assertEqual(len(terms), 1)
        self.assertEqual(next(iter(terms))["date_maturity"], self.move.invoice_date_due)

    def _assert_terms_close_on_the_document_total(self, move):
        subtotal = sum(move.invoice_line_ids.mapped("price_subtotal"))
        # The freight is in the document total, not in the line subtotal.
        self.assertNotAlmostEqual(abs(move.amount_total_signed), subtotal, places=2)
        payment_lines = move.line_ids.filtered(
            lambda line: line.display_type == "payment_term"
        )
        self.assertTrue(move.amount_total_signed)
        self.assertEqual(len(payment_lines), 2)
        self.assertAlmostEqual(
            sum(payment_lines.mapped("balance")), move.amount_total_signed, places=2
        )
        self.assertAlmostEqual(sum(move.line_ids.mapped("balance")), 0.0, places=2)

    def test_the_terms_include_the_freight_of_the_document(self):
        self.move.invoice_line_ids[0].freight_value = 50.0
        self.move.invoice_payment_term_id = self._split_term()

        self._assert_terms_close_on_the_document_total(self.move)

    def test_the_terms_include_the_freight_when_editing_the_term_in_a_form(self):
        self.move.invoice_line_ids[0].freight_value = 50.0
        with Form(self.move) as move_form:
            move_form.invoice_payment_term_id = self._split_term()

        self._assert_terms_close_on_the_document_total(self.move)

    def _not_in_the_financial_total(self):
        """The financial total is 0 for these lines, the document total is not."""
        line = self.move.invoice_line_ids[0]
        line.fiscal_operation_line_id.sudo().add_to_amount = False
        line.freight_value = 50.0
        self.move.invalidate_recordset()

    def test_the_terms_follow_the_document_total_not_the_financial_total(self):
        self._not_in_the_financial_total()
        self.move.invoice_payment_term_id = self._split_term()

        self._assert_terms_close_on_the_document_total(self.move)

    def test_the_terms_follow_the_document_total_when_editing_in_a_form(self):
        self._not_in_the_financial_total()
        with Form(self.move) as move_form:
            move_form.invoice_payment_term_id = self._split_term()

        self._assert_terms_close_on_the_document_total(self.move)
