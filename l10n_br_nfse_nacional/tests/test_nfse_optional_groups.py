# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase


class TestNfseOptionalGroups(TransactionCase):
    """What the DPS may not carry: a masked NBS code and an empty discount group.

    Both were found comparing a real NFS-e issued through the national web emitter
    against the one this module builds for the same taker and the same amount.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.line = cls.env.ref("l10n_br_nfse_nacional.demo_nfse_lc").fiscal_line_ids[0]
        cls.nbs = cls.env["l10n_br_fiscal.nbs"].search([("code", "!=", False)], limit=1)

    def test_the_nbs_code_goes_out_without_its_mask(self):
        """The catalog stores "1.2001.50.00" for display; the layout wants 9 digits."""
        self.line.nbs_id = self.nbs
        self.assertTrue(self.nbs.code)
        self.assertEqual(
            self.line.nfse10_cNBS,
            "".join(char for char in self.nbs.code if char.isdigit()),
        )
        self.assertNotIn(".", self.line.nfse10_cNBS)

    def test_without_an_nbs_the_tag_is_left_out(self):
        self.line.nbs_id = False
        self.assertFalse(self.line.nfse10_cNBS)

    def test_the_discount_group_is_absent_when_there_is_no_discount(self):
        """Pointing the group at the line always serializes an empty tag."""
        self.line.write({"discount_value": 0.0, "issqn_desc_cond_amount": 0.0})
        self.assertFalse(self.line.nfse10_vDescCondIncond)

    def test_an_unconditional_discount_brings_the_group_back(self):
        self.line.discount_value = 10.0
        self.assertEqual(self.line.nfse10_vDescCondIncond, self.line)
        self.assertEqual(self.line.nfse10_vDescIncond, "10.00")

    def test_a_conditional_discount_brings_the_group_back(self):
        self.line.write({"discount_value": 0.0, "issqn_desc_cond_amount": 7.5})
        self.assertEqual(self.line.nfse10_vDescCondIncond, self.line)
        self.assertEqual(self.line.nfse10_vDescCond, "7.50")
