# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase


class TestNfseIbsCbs(TransactionCase):
    """The IBS/CBS group the 1.01 layout added to the DPS.

    The group hangs off infDPS, not off the item, and the layout leaves both of
    its codes required, so the builder either produces the whole subtree or
    nothing at all.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document = cls.env.ref("l10n_br_nfse_nacional.demo_nfse_lc")
        cls.line = cls.document.fiscal_line_ids[0]
        cls.indicator = cls.env["l10n_br_fiscal.operation.indicator"].search(
            [("code", "=", "050103")], limit=1
        )

    def test_without_an_operation_indicator_the_group_is_left_out(self):
        """cIndOp has no default: guessing one would misplace the taxable event."""
        self.line.operation_indicator_id = False
        self.assertFalse(self.document._build_nfse10_ibscbs())

    def test_the_group_carries_the_operation_indicator(self):
        self.line.operation_indicator_id = self.indicator
        group = self.document._build_nfse10_ibscbs()
        self.assertEqual(group.cIndOp, "050103")
        self.assertEqual(group.finNFSe, "0")
        self.assertEqual(group.indDest, "0")

    def test_the_codes_fall_back_to_the_general_regime(self):
        self.line.write(
            {
                "operation_indicator_id": self.indicator.id,
                "tax_classification_id": False,
                "ibs_cst_id": False,
                "cbs_cst_id": False,
            }
        )
        gibscbs = self.document._build_nfse10_ibscbs().valores.trib.gIBSCBS
        self.assertEqual(gibscbs.CST, "000")
        self.assertEqual(gibscbs.cClassTrib, "000001")

    def test_a_tax_classification_overrides_both_codes(self):
        classification = self.env["l10n_br_fiscal.tax.classification"].search(
            [("code", "=", "200019")], limit=1
        )
        if not classification:
            self.skipTest("no tax classification 200019 in the database")
        self.line.write(
            {
                "operation_indicator_id": self.indicator.id,
                "tax_classification_id": classification.id,
                "ibs_cst_id": False,
                "cbs_cst_id": False,
            }
        )
        gibscbs = self.document._build_nfse10_ibscbs().valores.trib.gIBSCBS
        self.assertEqual(gibscbs.cClassTrib, "200019")
        self.assertEqual(gibscbs.CST, "200")

    def test_the_final_consumer_flag_comes_from_the_document(self):
        self.line.operation_indicator_id = self.indicator
        self.document.ind_final = "1"
        self.assertEqual(self.document._build_nfse10_ibscbs().indFinal, "1")


class TestNfsePisCofinsWithholding(TransactionCase):
    """tpRetPisCofins tells the taker which of PIS, COFINS and CSLL were held.

    The schema table repeats itself: codes 1 and 2 say nothing about the CSLL,
    while 0 and 3 to 9 already name all eight combinations, so only those are
    ever emitted.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.line = cls.env.ref("l10n_br_nfse_nacional.demo_nfse_lc").fiscal_line_ids[0]

    def _withhold(self, pis, cofins, csll):
        self.line.write(
            {
                "pis_wh_value": 100.0 if pis else 0.0,
                "cofins_wh_value": 100.0 if cofins else 0.0,
                "csll_wh_value": 100.0 if csll else 0.0,
            }
        )
        return self.line.nfse10_tpRetPisCofins

    def test_nothing_withheld(self):
        self.assertEqual(self._withhold(False, False, False), "0")

    def test_all_three_withheld(self):
        self.assertEqual(self._withhold(True, True, True), "3")

    def test_pis_and_cofins_withheld(self):
        self.assertEqual(self._withhold(True, True, False), "4")

    def test_only_pis_withheld(self):
        self.assertEqual(self._withhold(True, False, False), "5")

    def test_only_cofins_withheld(self):
        self.assertEqual(self._withhold(False, True, False), "6")

    def test_cofins_and_csll_withheld(self):
        self.assertEqual(self._withhold(False, True, True), "7")

    def test_only_csll_withheld(self):
        self.assertEqual(self._withhold(False, False, True), "8")

    def test_pis_and_csll_withheld(self):
        self.assertEqual(self._withhold(True, False, True), "9")

    def test_every_combination_has_its_own_code(self):
        codes = {
            self._withhold(pis, cofins, csll)
            for pis in (False, True)
            for cofins in (False, True)
            for csll in (False, True)
        }
        self.assertEqual(len(codes), 8)


class TestNfseFederalWithholding(TransactionCase):
    """What tribFed and totTrib carry once the taker withholds.

    Values checked against a real NFS-e issued through the national web emitter
    for a service of 201890.09 with CSRF and IRRF withheld at source.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.line = cls.env.ref("l10n_br_nfse_nacional.demo_nfse_lc").fiscal_line_ids[0]
        cls.line.write(
            {
                "irpj_wh_value": 2018.90,
                "csll_wh_value": 2018.90,
                "pis_wh_value": 1312.29,
                "cofins_wh_value": 6056.70,
                "issqn_value": 5047.25,
            }
        )

    def test_the_csrf_goes_out_as_a_single_amount(self):
        """tribFed has no monetary field for the PIS/COFINS withheld."""
        self.assertEqual(self.line.nfse10_vRetCSLL, "9387.89")

    def test_the_irrf_stays_on_its_own_field(self):
        self.assertEqual(self.line.nfse10_vRetIRRF, "2018.90")

    def test_the_federal_total_is_every_federal_withholding(self):
        self.assertEqual(self.line.nfse10_vTotTribFed, "11406.79")

    def test_the_municipal_total_is_the_issqn(self):
        self.assertEqual(self.line.nfse10_vTotTribMun, "5047.25")

    def test_nothing_withheld_leaves_the_retention_tags_out(self):
        self.line.write(
            {
                "irpj_wh_value": 0.0,
                "csll_wh_value": 0.0,
                "pis_wh_value": 0.0,
                "cofins_wh_value": 0.0,
            }
        )
        self.assertFalse(self.line.nfse10_vRetCSLL)
        self.assertFalse(self.line.nfse10_vRetIRRF)
        self.assertEqual(self.line.nfse10_vTotTribFed, "0.00")

    def test_only_the_csll_withheld_still_fills_vretcsll(self):
        self.line.write(
            {
                "irpj_wh_value": 0.0,
                "csll_wh_value": 100.0,
                "pis_wh_value": 0.0,
                "cofins_wh_value": 0.0,
            }
        )
        self.assertEqual(self.line.nfse10_vRetCSLL, "100.00")
        self.assertEqual(self.line.nfse10_vTotTribFed, "100.00")


class TestNfseCompetence(TransactionCase):
    """dCompet is the competence of the service, not the day of issue."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document = cls.env.ref("l10n_br_nfse_nacional.demo_nfse_lc")

    def test_the_competence_follows_the_service_date(self):
        self.document.write(
            {
                "document_date": "2026-10-01 12:00:00",
                "date_in_out": "2026-09-30 12:00:00",
            }
        )
        self.assertEqual(self.document.nfse10_dCompet, "2026-09-30")
        self.assertTrue(self.document.nfse10_dhEmi.startswith("2026-10-01"))

    def test_without_a_service_date_the_issue_date_answers(self):
        self.document.write(
            {"document_date": "2026-10-01 12:00:00", "date_in_out": False}
        )
        self.assertEqual(self.document.nfse10_dCompet, "2026-10-01")
