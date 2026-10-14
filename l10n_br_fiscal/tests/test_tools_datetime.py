# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from datetime import datetime, timedelta, timezone

from xsdata.models.datatype import XmlDateTime

from odoo.tests import TransactionCase

from odoo.addons.l10n_br_fiscal.tools import to_utc_naive_datetime_string


class TestToUtcNaiveDatetimeString(TransactionCase):
    def test_aware_offset_converted_to_utc(self):
        value = datetime(2026, 10, 13, 8, 45, 28, tzinfo=timezone(timedelta(hours=-3)))
        self.assertEqual(to_utc_naive_datetime_string(value), "2026-10-13 11:45:28")

    def test_iso_string_with_offset(self):
        self.assertEqual(
            to_utc_naive_datetime_string("2026-10-13T08:45:28-03:00"),
            "2026-10-13 11:45:28",
        )

    def test_day_rollover(self):
        self.assertEqual(
            to_utc_naive_datetime_string("2026-10-13T22:30:00-03:00"),
            "2026-10-14 01:30:00",
        )

    def test_xml_datetime(self):
        value = XmlDateTime.from_string("2026-10-13T08:45:28-03:00")
        self.assertEqual(to_utc_naive_datetime_string(value), "2026-10-13 11:45:28")

    def test_naive_unchanged(self):
        self.assertEqual(
            to_utc_naive_datetime_string(datetime(2026, 10, 13, 8, 45, 28)),
            "2026-10-13 08:45:28",
        )
        self.assertEqual(
            to_utc_naive_datetime_string("2026-10-13T08:45:28"),
            "2026-10-13 08:45:28",
        )

    def test_empty(self):
        self.assertFalse(to_utc_naive_datetime_string(False))
        self.assertFalse(to_utc_naive_datetime_string(None))
