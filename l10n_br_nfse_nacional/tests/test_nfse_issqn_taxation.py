# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase


class TestNfseTribIssqnMapping(TransactionCase):
    """TSTribISSQN (tiposSimples_v1.01.xsd): 1 taxable, 2 immunity,

    3 export of service, 4 no incidence. This is a different enum from the
    ABRASF ISSQN_TO_TRIBUTACAO_ISS: its 2 and 3 name the opposite situations.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.line = cls.env.ref("l10n_br_nfse_nacional.demo_nfse_lc").fiscal_line_ids[0]

    def test_each_issqn_eligibility_maps_to_its_trib_issqn(self):
        expected = {
            "1": "1",
            "2": "4",
            "3": "1",
            "4": "3",
            "5": "2",
            "6": "1",
            "7": "1",
        }
        for eligibility, trib_issqn in expected.items():
            self.line.issqn_eligibility = eligibility
            self.assertEqual(self.line.nfse10_tribISSQN, trib_issqn)

    def test_a_new_line_is_taxable_and_not_exempt(self):
        line = self.env["l10n_br_fiscal.document.line"].new({})
        self.assertEqual(line.issqn_eligibility, "1")
        self.assertEqual(line.nfse10_tribISSQN, "1")


class TestNfseIssqnSituationGroups(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.line = cls.env.ref("l10n_br_nfse_nacional.demo_nfse_lc").fiscal_line_ids[0]
        cls.abroad = cls.env.ref("base.es")

    def test_com_ext_only_appears_for_export(self):
        self.line.issqn_eligibility = "4"
        self.assertEqual(self.line.nfse10_comExt, self.line)

        self.line.issqn_eligibility = "1"
        self.assertFalse(self.line.nfse10_comExt)

    def test_bm_only_appears_for_exemption(self):
        self.line.issqn_eligibility = "3"
        self.assertEqual(self.line.nfse10_BM, self.line)

        self.line.issqn_eligibility = "1"
        self.assertFalse(self.line.nfse10_BM)

    def test_exig_susp_only_appears_for_suspended_liability(self):
        self.line.issqn_eligibility = "6"
        self.assertEqual(self.line.nfse10_exigSusp, self.line)

        self.line.issqn_eligibility = "7"
        self.assertEqual(self.line.nfse10_exigSusp, self.line)

        self.line.issqn_eligibility = "1"
        self.assertFalse(self.line.nfse10_exigSusp)

    def test_tp_susp_follows_judicial_or_administrative(self):
        self.line.issqn_eligibility = "6"
        self.assertEqual(self.line.nfse10_tpSusp, "1")

        self.line.issqn_eligibility = "7"
        self.assertEqual(self.line.nfse10_tpSusp, "2")

        self.line.issqn_eligibility = "1"
        self.assertFalse(self.line.nfse10_tpSusp)

    def test_tp_imunidade_defaults_to_unspecified(self):
        self.line.issqn_eligibility = "5"
        self.assertEqual(self.line.nfse10_tpImunidade, "0")

        self.line.issqn_eligibility = "1"
        self.assertFalse(self.line.nfse10_tpImunidade)

    def test_c_pais_result_comes_from_the_taker_country(self):
        self.line.partner_id.country_id = self.abroad
        self.line.issqn_eligibility = "4"
        self.assertEqual(self.line.nfse10_cPaisResult, self.abroad.code)

        self.line.issqn_eligibility = "1"
        self.assertFalse(self.line.nfse10_cPaisResult)


class TestNfseIssqnBusinessErrors(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.document = cls.env.ref("l10n_br_nfse_nacional.demo_nfse_lc")
        cls.line = cls.document.fiscal_line_ids[0]
        cls.abroad = cls.env.ref("base.es")

    def test_export_without_com_ext_is_reported(self):
        self.line.issqn_eligibility = "4"
        errors = self.document._nfse10_business_errors()
        self.assertTrue(errors)

    def test_export_with_com_ext_filled_is_not_reported(self):
        self.line.partner_id.country_id = self.abroad
        self.line.write(
            {
                "issqn_eligibility": "4",
                "nfse10_mdPrestacao": "1",
                "nfse10_vincPrest": "0",
                "nfse10_tpMoeda": "220",
                "nfse10_vServMoeda": "20.00",
                "nfse10_mecAFComexP": "01",
                "nfse10_mecAFComexT": "01",
                "nfse10_movTempBens": "1",
                "nfse10_mdic": "0",
            }
        )
        self.assertFalse(self.document._nfse10_business_errors())

    def test_suspended_liability_without_a_process_number_is_reported(self):
        self.line.issqn_eligibility = "6"
        errors = self.document._nfse10_business_errors()
        self.assertTrue(errors)

    def test_suspended_liability_with_a_process_number_is_not_reported(self):
        self.line.write(
            {
                "issqn_eligibility": "6",
                "nfse10_nProcesso": "1" * 30,
            }
        )
        self.assertFalse(self.document._nfse10_business_errors())

    def test_exemption_without_a_benefit_is_reported(self):
        self.line.issqn_eligibility = "3"
        errors = self.document._nfse10_business_errors()
        self.assertTrue(errors)

    def test_exemption_with_a_benefit_is_not_reported(self):
        self.line.write(
            {
                "issqn_eligibility": "3",
                "nfse10_nBM": "1" * 14,
                "nfse10_pRedBCBM": "100.00",
            }
        )
        self.assertFalse(self.document._nfse10_business_errors())


class TestNfseExportedServiceSchema(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.document = cls.env.ref("l10n_br_nfse_nacional.demo_nfse_lc")
        cls.line = cls.document.fiscal_line_ids[0]

    def test_an_export_of_service_with_com_ext_validates(self):
        self.line.partner_id.country_id = self.env.ref("base.es")
        self.line.write(
            {
                "issqn_eligibility": "4",
                "nfse10_mdPrestacao": "1",
                "nfse10_vincPrest": "0",
                "nfse10_tpMoeda": "220",
                "nfse10_vServMoeda": "20.00",
                "nfse10_mecAFComexP": "01",
                "nfse10_mecAFComexT": "01",
                "nfse10_movTempBens": "1",
                "nfse10_mdic": "0",
            }
        )
        xml = self.document._serialize([])[0].to_xml()
        self.assertEqual(self.document._nfse10_schema_errors(xml), [])
