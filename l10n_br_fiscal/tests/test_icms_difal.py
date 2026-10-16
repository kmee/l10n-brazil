# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests import TransactionCase, tagged

from ..constants.fiscal import (
    FINAL_CUSTOMER_NO,
    FINAL_CUSTOMER_YES,
    NFE_IND_IE_DEST_1,
    NFE_IND_IE_DEST_9,
)
from ..constants.icms import ICMS_ORIGIN_DEFAULT
from .tools import load_fiscal_fixture_files


@tagged("post_install", "-at_install")
class TestIcmsDifal(TransactionCase):
    """ICMS DIFAL on interstate sales of 100.00 from a company in SP.

    Rates used in the expected values (ICMS regulation data):
    SP to MG interstate 12%, MG internal 18%, MG FCP 2% (MG uses the
    double base); SP to PE interstate 7%, PE internal 20.5%, PE FCP 2%
    (PE uses the single base).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        load_fiscal_fixture_files(cls.env)
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.company.icms_regulation_id = cls.env.ref(
            "l10n_br_fiscal.tax_icms_regulation"
        )
        country = cls.env.ref("base.br")
        state_mg = cls.env.ref("base.state_br_mg")
        state_pe = cls.env.ref("base.state_br_pe")
        cls.mg_non_taxpayer = cls.env["res.partner"].create(
            {
                "name": "DIFAL MG non-taxpayer",
                "country_id": country.id,
                "state_id": state_mg.id,
                "fiscal_profile_id": cls.env.ref(
                    "l10n_br_fiscal.partner_fiscal_profile_pfnc"
                ).id,
                "ind_ie_dest": NFE_IND_IE_DEST_9,
            }
        )
        cls.mg_taxpayer = cls.env["res.partner"].create(
            {
                "name": "DIFAL MG taxpayer",
                "is_company": True,
                "country_id": country.id,
                "state_id": state_mg.id,
                "fiscal_profile_id": cls.env.ref(
                    "l10n_br_fiscal.partner_fiscal_profile_cnt"
                ).id,
                "ind_ie_dest": NFE_IND_IE_DEST_1,
            }
        )
        cls.pe_non_taxpayer = cls.env["res.partner"].create(
            {
                "name": "DIFAL PE non-taxpayer",
                "country_id": country.id,
                "state_id": state_pe.id,
                "fiscal_profile_id": cls.env.ref(
                    "l10n_br_fiscal.partner_fiscal_profile_pfnc"
                ).id,
                "ind_ie_dest": NFE_IND_IE_DEST_9,
            }
        )
        cls.tax_icms_7 = cls.env.ref("l10n_br_fiscal.tax_icms_7")
        cls.tax_icms_12 = cls.env.ref("l10n_br_fiscal.tax_icms_12")
        cls.tax_icmsfcp_2 = cls.env.ref("l10n_br_fiscal.tax_icmsfcp_2")

    def _compute(self, taxes, partner, ind_final):
        return taxes.compute_taxes(
            company=self.company,
            partner=partner,
            product=self.env.ref("product.product_product_12"),
            price_unit=100.0,
            quantity=1.0,
            uom_id=self.env.ref("uom.product_uom_unit"),
            fiscal_price=100.0,
            fiscal_quantity=1.0,
            uot_id=self.env.ref("uom.product_uom_unit"),
            discount_value=0.0,
            insurance_value=0.0,
            other_value=0.0,
            freight_value=0.0,
            ii_customhouse_charges=0.0,
            ii_iof_value=0.0,
            ncm=self.env.ref("l10n_br_fiscal.ncm_72132000"),
            nbs=self.env["l10n_br_fiscal.nbs"],
            nbm=self.env["l10n_br_fiscal.nbm"],
            cest=self.env["l10n_br_fiscal.cest"],
            operation_line=self.env.ref("l10n_br_fiscal.fo_venda_venda"),
            cfop=self.env.ref("l10n_br_fiscal.cfop_6102"),
            icms_origin=ICMS_ORIGIN_DEFAULT,
            icms_cst_id=self.env.ref("l10n_br_fiscal.cst_icms_00"),
            ind_final=ind_final,
        )["taxes"]

    def test_difal_taxpayer_final_consumer_double_base(self):
        """Taxpayer buying for use or consumption in MG: double base.

        With FCP: base = (100.00 - 12.00) / (1 - (18% + 2%)) = 88 / 0.80
        = 110.00; ICMS MG = 110.00 x 18% = 19.80; DIFAL = 19.80 - 12.00
        = 7.80; FCP = 110.00 x 2% = 2.20.
        Without FCP: base = 88 / 0.82 = 107.3170... = 107.32;
        ICMS MG = 107.32 x 18% = 19.3176 = 19.32; DIFAL = 19.32 - 12.00
        = 7.32.
        """
        self.assertEqual(self.mg_taxpayer.ind_ie_dest, NFE_IND_IE_DEST_1)
        taxes = self._compute(
            self.tax_icms_12 | self.tax_icmsfcp_2,
            self.mg_taxpayer,
            FINAL_CUSTOMER_YES,
        )
        self.assertAlmostEqual(taxes["icms"]["tax_value"], 12.00, places=2)
        self.assertAlmostEqual(taxes["icms"]["icms_dest_perc"], 18.0, places=2)
        self.assertAlmostEqual(taxes["icms"]["icms_dest_base"], 110.00, places=2)
        self.assertAlmostEqual(taxes["icms"]["icms_dest_value"], 7.80, places=2)
        self.assertAlmostEqual(taxes["icmsfcp"]["base"], 110.00, places=2)
        self.assertAlmostEqual(taxes["icmsfcp"]["tax_value"], 2.20, places=2)

        taxes = self._compute(self.tax_icms_12, self.mg_taxpayer, FINAL_CUSTOMER_YES)
        self.assertAlmostEqual(taxes["icms"]["icms_dest_base"], 107.32, places=2)
        self.assertAlmostEqual(taxes["icms"]["icms_dest_value"], 7.32, places=2)

    def test_difal_taxpayer_resale(self):
        """Taxpayer buying for resale (not a final consumer): no DIFAL.

        Only the interstate ICMS remains: 100.00 x 12% = 12.00.
        """
        self.assertEqual(self.mg_taxpayer.ind_ie_dest, NFE_IND_IE_DEST_1)
        taxes = self._compute(self.tax_icms_12, self.mg_taxpayer, FINAL_CUSTOMER_NO)
        self.assertAlmostEqual(taxes["icms"]["tax_value"], 12.00, places=2)
        self.assertAlmostEqual(taxes["icms"]["icms_dest_base"], 0.00, places=2)
        self.assertAlmostEqual(taxes["icms"]["icms_dest_value"], 0.00, places=2)

    def test_difal_company_without_icms_regulation(self):
        """Company without ICMS regulation: no error and no DIFAL.

        Only the interstate ICMS remains: 100.00 x 12% = 12.00.
        """
        self.company.icms_regulation_id = False
        taxes = self._compute(
            self.tax_icms_12, self.mg_non_taxpayer, FINAL_CUSTOMER_YES
        )
        self.assertAlmostEqual(taxes["icms"]["tax_value"], 12.00, places=2)
        self.assertAlmostEqual(taxes["icms"]["icms_dest_value"], 0.00, places=2)

    def test_difal_non_taxpayer_single_base_state(self):
        """Non-taxpayer in PE (single base state): unchanged behavior.

        Base = 100.00; ICMS PE = 100.00 x 20.5% = 20.50; ICMS SP = 100.00
        x 7% = 7.00; DIFAL = 20.50 - 7.00 = 13.50; FCP = 100.00 x 2% = 2.00.
        The partner keeps the default "not a final consumer" flag: a
        non-taxpayer always owes DIFAL.
        """
        taxes = self._compute(
            self.tax_icms_7 | self.tax_icmsfcp_2,
            self.pe_non_taxpayer,
            FINAL_CUSTOMER_NO,
        )
        self.assertAlmostEqual(taxes["icms"]["tax_value"], 7.00, places=2)
        self.assertAlmostEqual(taxes["icms"]["icms_dest_base"], 100.00, places=2)
        self.assertAlmostEqual(taxes["icms"]["icms_dest_value"], 13.50, places=2)
        self.assertAlmostEqual(taxes["icmsfcp"]["tax_value"], 2.00, places=2)
