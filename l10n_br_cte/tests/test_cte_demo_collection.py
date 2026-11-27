# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from datetime import timedelta

from freezegun import freeze_time

from odoo import fields
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCteDemoCollection(TransactionCase):
    """The CT-e of the demo that is complete and has a collection of two
    installments: it shows no XML validation error."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document = cls.env.ref("l10n_br_cte.demo_cte_lc_modal_rodoviario_cobranca")

    def test_the_xml_of_the_demo_has_no_validation_error(self):
        self.assertFalse(self.document.xml_error_message)

    def test_the_demo_has_the_two_installments_of_the_collection(self):
        # the demo counts the days from the local day of its issue date; the day of
        # the test run may be another one (the loading and the tests can fall on
        # each side of midnight)
        issue_day = self.document._get_cte_reference_date()
        duplicates = self.document.cte40_cobr.cte40_dup.sorted("cte40_nDup")
        self.assertEqual(duplicates.mapped("cte40_nDup"), ["001", "002"])
        self.assertEqual(
            [(dup.cte40_dVenc - issue_day).days for dup in duplicates], [30, 60]
        )
        self.assertAlmostEqual(
            sum(duplicates.mapped("cte40_vDup")),
            self.document.amount_financial_total,
            places=2,
        )
        self.assertEqual(len(self.document._edi_display_installments()), 2)
        self.assertTrue(self.document.edi_payment_summary)

    def test_the_due_days_do_not_depend_on_the_day_the_tests_run(self):
        """The demo was loaded on a day and the tests may run on another one,
        even right after midnight: the due days count from the issue date."""
        duplicates = self.document.cte40_cobr.cte40_dup.sorted("cte40_nDup")
        later = fields.Datetime.now() + timedelta(days=2, hours=5)
        with freeze_time(later):
            issue_day = self.document._get_cte_reference_date()
            self.assertEqual(
                [(dup.cte40_dVenc - issue_day).days for dup in duplicates], [30, 60]
            )
            self.assertNotEqual(issue_day, fields.Date.context_today(self.document))
