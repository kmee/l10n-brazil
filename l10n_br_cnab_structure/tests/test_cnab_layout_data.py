# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import tagged
from odoo.tests.common import TransactionCase


@tagged("post_install", "-at_install")
class TestCnabLayoutData(TransactionCase):
    def test_batch_error_occurrence_code_is_ascii(self):
        """The bank returns 'HA' (batch error), not the accented 'HÁ'."""
        for bank in ("itau", "bb", "santander"):
            structure = self.env.ref(f"l10n_br_cnab_structure.cnab_{bank}_240")
            occurrences = self.env["cnab.occurrence"].search(
                [("cnab_structure_id", "=", structure.id)]
            )
            codes = occurrences.mapped("code")
            self.assertIn("HA", codes, bank)
            self.assertNotIn("HÁ", codes, bank)

    def test_segment_j_discount_has_two_decimals(self):
        """The J discount (115-129) is 9(13)V9(02): amounts keep the cents."""
        for bank in ("itau", "bb", "santander", "sicoob"):
            field = self.env.ref(
                f"l10n_br_cnab_structure.cnab_{bank}_240_boleto_segmento_j_115_129"
            )
            self.assertEqual(field.assumed_comma, 2, bank)
