# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import time
from datetime import date

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


class FakePaymentLine:
    """Minimal stand-in for an account.payment.line read by the CNAB fields."""

    def __init__(self, due_date, pay_date):
        self.ml_maturity_date = due_date
        self.date = pay_date


@tagged("post_install", "-at_install")
class TestCnabSegmentDates(TransactionCase):
    DUE_DATE = date(2026, 10, 30)
    PAY_DATE = date(2026, 10, 28)

    def _output(self, xml_id, line):
        field = self.env.ref(f"l10n_br_cnab_structure.{xml_id}")
        return field.output(line)[1]

    def test_dated_fields_use_the_line_date(self):
        """Fields fed by a payment line date must not always send today."""
        fields = self.env["l10n_br_cnab.line.field"].search(
            [
                ("content_source_field", "in", ("date", "ml_maturity_date")),
                ("sending_dynamic_content", "ilike", "strftime"),
            ]
        )
        self.assertTrue(fields)
        for field in fields:
            self.assertIn(
                "content",
                field.sending_dynamic_content.replace("time.strftime", ""),
                f"{field.display_name} ignores the line date (always today)",
            )

    def test_segment_j_dates_come_from_the_line(self):
        """Due date (92-99) and payment date (145-152) of segment J, per bank."""
        line = FakePaymentLine(self.DUE_DATE, self.PAY_DATE)
        for prefix in (
            "cnab_itau_240",
            "cnab_bb_240",
            "cnab_santander_240",
            "cnab_sicoob_240",
        ):
            self.assertEqual(
                self._output(f"{prefix}_boleto_segmento_j_92_99", line),
                "30102026",
                prefix,
            )
            self.assertEqual(
                self._output(f"{prefix}_boleto_segmento_j_145_152", line),
                "28102026",
                prefix,
            )

    def test_segment_o_and_oct_dates_come_from_the_line(self):
        line = FakePaymentLine(self.DUE_DATE, self.PAY_DATE)
        cases = {
            "cnab_itau_240_conc_tributo_bc_segmento_o_96_103": "30102026",
            "cnab_bb_240_conc_tributo_bc_segmento_o_92_99": "30102026",
            "cnab_santander_240_conc_tributo_bc_segmento_o_92_99": "30102026",
            "cnab_santander_240_conc_tributo_bc_segmento_o_100_107": "28102026",
            "cnab_sicoob_240_conc_tributo_bc_segmento_o_92_99": "30102026",
            "cnab_santander_240_oct_segmento_i_128_135": "28102026",
            "cnab_santander_240_pix_qr_segmento_j_145_152": "28102026",
        }
        for xml_id, expected in cases.items():
            self.assertEqual(self._output(xml_id, line), expected, xml_id)

    def test_segment_j_dates_fall_back_to_today(self):
        """Without a date on the line the field keeps sending today's date."""
        line = FakePaymentLine(False, False)
        today = time.strftime("%d%m%Y")
        for prefix in ("cnab_itau_240", "cnab_bb_240", "cnab_sicoob_240"):
            self.assertEqual(
                self._output(f"{prefix}_boleto_segmento_j_92_99", line), today
            )

    def test_itau_segment_j_currency_quantity_is_zeros(self):
        """Positions 168-182 of the Itau segment J are numeric: zeros, not blanks."""
        field = self.env.ref(
            "l10n_br_cnab_structure.cnab_itau_240_boleto_segmento_j_168_182"
        )
        self.assertEqual(field.type, "num")
        self.assertEqual(field.output(None)[1], "0" * 15)
