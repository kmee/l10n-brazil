# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged


@tagged("icms")
class TestIcmsDifalLabels(TransactionCase):
    def test_difal_percent_labels_match_the_values(self):
        """icms_origin_percent keeps the interstate rate (pICMSInter) and
        icms_destination_percent the internal rate of the destination state
        (pICMSUFDest): the labels must say so."""
        fields_info = self.env["l10n_br_fiscal.document.line"].fields_get(
            ["icms_origin_percent", "icms_destination_percent"], ["string"]
        )
        self.assertEqual(fields_info["icms_origin_percent"]["string"], "ICMS External %")
        self.assertEqual(
            fields_info["icms_destination_percent"]["string"], "ICMS Internal %"
        )
