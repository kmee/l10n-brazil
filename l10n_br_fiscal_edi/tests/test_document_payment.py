# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import date
from unittest.mock import patch

from ..tools import EdiInstallment, EdiPayment
from .common import EdiImportCase


class TestDocumentPayment(EdiImportCase):
    """The page of installments and payments of the document."""

    def _document(self, installments=(), payments=(), **values):
        """Imported document whose type declares the given installments and
        payments, as a reader would."""
        document = self._create_imported_document(
            lines=[
                {
                    "quantity": 2.0,
                    "price_unit": 50.0,
                    "fiscal_operation_line_id": self.env.ref(
                        "l10n_br_fiscal.fo_compras_compras"
                    ).id,
                }
            ],
            **values,
        )
        document_model = type(self.Document)
        patchers = [
            patch.object(
                document_model, "_edi_get_installments", lambda doc: list(installments)
            ),
            patch.object(
                document_model, "_edi_get_payments", lambda doc: list(payments)
            ),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        document.invalidate_recordset()
        return document

    def _installments(self, amounts):
        return [
            EdiInstallment(f"{n + 1:03d}", date(2026, 12 + 0, 10 + n), amount)
            for n, amount in enumerate(amounts)
        ]

    def test_a_document_that_declares_nothing_has_no_page(self):
        document = self._document()
        self.assertFalse(document.edi_payment_summary)

    def test_the_installments_and_the_payments_are_shown_as_declared(self):
        document = self._document(
            installments=self._installments([60.0, 40.0]),
            payments=[EdiPayment("01", 100.0, "installments")],
        )
        summary = str(document.edi_payment_summary)
        for text in ("001", "002", "60.00", "40.00", "12/10/2026", "12/11/2026"):
            self.assertIn(text, summary)
        self.assertIn("01", summary)
        self.assertIn("In installments", summary)

    def test_a_payment_that_is_other_says_what_it_is(self):
        document = self._document(
            payments=[EdiPayment("99", 100.0, "cash", description="Barter")]
        )
        summary = str(document.edi_payment_summary)
        self.assertIn("Barter", summary)
        self.assertIn("Cash", summary)

    def test_installments_that_add_up_raise_no_warning(self):
        document = self._document()
        net = document.amount_financial_total
        self.assertTrue(net, "the net amount payable of the document is zero")
        document = self._document(installments=self._installments([net - 10, 10]))
        self.assertFalse(document._edi_installment_difference())
        self.assertNotIn("add up", str(document.edi_payment_summary))
        self.assertFalse(document.import_warning)

    def test_installments_that_do_not_add_up_raise_a_warning(self):
        net = self._document().amount_financial_total
        document = self._document(installments=self._installments([net - 20]))
        self.assertEqual(document._edi_installment_difference(), 20.0)
        self.assertIn("add up", str(document.edi_payment_summary))
        self.assertIn("The declared installments add up to", document.import_warning)
        self.assertIn(f"{net - 20:.2f}", document.import_warning)

    def test_withholdings_and_the_net_amount_are_shown_with_no_installment(self):
        """A service document declares no installment, but the page shows what the
        company retains and what it pays."""
        document = self._document()
        document.fiscal_line_ids.issqn_wh_value = 5.0
        document.invalidate_recordset()
        self.assertTrue(document.amount_tax_withholding)
        summary = str(document.edi_payment_summary)
        self.assertIn("Withholdings", summary)
        self.assertIn("Net amount payable", summary)
        self.assertNotIn("Installments", summary.replace("In installments", ""))

    def test_the_page_only_reads(self):
        """Computing the page writes nothing, in the document or elsewhere."""
        document = self._document(installments=self._installments([100.0]))
        write_date = document.write_date
        with patch.object(
            type(self.Document), "write", side_effect=AssertionError("wrote")
        ):
            document.invalidate_recordset()
            self.assertTrue(document.edi_payment_summary)
        self.assertEqual(document.write_date, write_date)

    def test_what_the_page_shows_can_differ_from_what_the_document_declares(self):
        document = self._document(installments=self._installments([100.0]))
        shown = [EdiInstallment("001", date(2027, 1, 5), 100.0)]
        with patch.object(
            type(self.Document), "_edi_display_installments", lambda doc: shown
        ):
            document.invalidate_recordset()
            self.assertIn("01/05/2027", str(document.edi_payment_summary))
