# Copyright 2026 Akretion - Raphaël Valyi <raphael.valyi@akretion.com>
# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError

from .test_nfse_serialize import TestNfseSerialize


class TestNfseExportLC(TestNfseSerialize):
    @classmethod
    def setUpClass(cls):
        nfse_list = [
            {
                "record_ref": "l10n_br_nfse_nacional.demo_nfse_lc",
                "xml_file": "dps-regime-normal.xml",
            }
        ]
        super().setUpClass(nfse_list)

    def test_serialize_xml(self):
        for nfse_data in self.nfse_list:
            nfse_data[
                "nfse"
            ].document_key = "420240420000000000000000007000000000000002"
            nfse_data["nfse"].document_serie = "00007"
            nfse_data["nfse"].rps_number = "2"
            diff = self.serialize_xml(nfse_data)
            self.assertEqual(len(diff), 0)

    def test_tot_trib_uses_the_monetary_group(self):
        """Outside Simples Nacional the burden goes in vTotTrib as an amount.

        Informing indTotTrib or pTotTribSN is what the national environment
        rejects with E0713, and the national web emitter declares the amounts,
        which is what the taker reconciles against vTotalRet.
        """
        line = self.nfse_list[0]["nfse"].fiscal_line_ids[0]
        self.assertFalse(line.nfse10_indTotTrib)
        self.assertFalse(line.nfse10_pTotTribSN)
        self.assertFalse(line.nfse10_pTotTrib)
        self.assertTrue(line.nfse10_vTotTrib)
        self.assertEqual(line.nfse10_vTotTribEst, "0.00")

    def test_dps_key_is_composed_from_the_document(self):
        """The DPS key is composed by the module, never typed by hand.

        Without it the Id of infDPS comes out empty, the reference of the
        signature points to nothing and the DPS is refused by the schema.
        """
        nfse = self.nfse_list[0]["nfse"]
        nfse.document_serie = "00007"
        nfse.rps_number = "2"
        nfse.document_key = False
        nfse._ensure_dps_key()
        self.assertEqual(len(nfse.document_key), 42)
        self.assertTrue(nfse.document_key.endswith("2".zfill(15)))
        self.assertEqual(nfse.nfse10_Id, f"DPS{nfse.document_key}")

    def test_send_refuses_an_invalid_xml_out_loud(self):
        """A pending schema error must stop the send with a message.

        Skipping in silence left the user pressing Send with nothing happening:
        no state change, no message in the chatter, no error on screen.
        """
        nfse = self.nfse_list[0]["nfse"]
        nfse.xml_error_message = "erro de esquema deixado de proposito"
        with self.assertRaises(UserError):
            nfse._eletronic_document_send()

    def test_paliq_stays_out_of_trib_mun(self):
        """pAliq is never exported, even with an ISSQN rate on the line.

        The rate lives in the municipality register inside the ADN, which
        applies it to the declared base. Sending it again only creates a
        divergence the day the municipality changes it.
        """
        line = self.nfse_list[0]["nfse"].fiscal_line_ids[0]
        line.issqn_percent = 2.5
        self.assertFalse(line.nfse10_pAliq)

    def test_dhemi_matches_local_timezone(self):
        nfse = self.nfse_list[0]["nfse"]
        self.assertEqual(nfse.nfse10_dhEmi, "2023-09-09T09:42:06-03:00")
