# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase


class TestNfseExportedService(TransactionCase):
    """A taker abroad carries its own tax number, or the reason it has none."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.abroad = cls.env["res.partner"].create(
            {
                "name": "Tomador no exterior",
                "is_company": True,
                "country_id": cls.env.ref("base.es").id,
            }
        )

    def test_a_taker_abroad_carries_its_own_tax_number(self):
        self.abroad.vat = "ESA58818501"
        self.assertEqual(self.abroad.nfse10_NIF, "ESA58818501")
        self.assertFalse(self.abroad.nfse10_cNaoNIF)

    def test_a_taker_abroad_without_a_tax_number_says_why(self):
        self.abroad.nif_motive_absence = "2"
        self.assertFalse(self.abroad.nfse10_NIF)
        self.assertEqual(self.abroad.nfse10_cNaoNIF, "2")

        self.abroad.nif_motive_absence = False
        self.assertEqual(self.abroad.nfse10_cNaoNIF, "1")
