# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from nfelib.nfse.bindings.v1_0.dps_v1_01 import Dps

from odoo.tests.common import TransactionCase, tagged

from odoo.addons.l10n_br_nfse_nacional.models.document import (
    nfse_nacional_schema_path,
)


@tagged("post_install", "-at_install")
class TestNfseSchema(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def _assert_valid(self, xml_id):
        document = self.env.ref(xml_id, raise_if_not_found=False)
        if not document:
            self.skipTest("l10n_br_nfse_nacional demo data is not installed")
        xml = document._serialize([])[0].to_xml()
        self.assertEqual(document._nfse10_schema_errors(xml), [])

    def test_dps_simples_nacional_validates(self):
        self._assert_valid("l10n_br_nfse_nacional.demo_nfse_sn")

    def test_dps_regime_normal_validates(self):
        self._assert_valid("l10n_br_nfse_nacional.demo_nfse_lc")

    def test_the_broken_serie_pattern_is_the_only_error_dropped(self):
        """The 1.01 schema cannot validate any numeric serie.

        TSSerieDPS carries the pattern "^0{0,4}\\d{1,5}$", and XML Schema reads
        "^" and "$" as literal characters rather than anchors. With maxLength 5
        only a value such as "^7$" would ever match, so the raw validation still
        reports the serie while _nfse10_schema_errors drops that one error.
        """
        document = self.env.ref(
            "l10n_br_nfse_nacional.demo_nfse_lc", raise_if_not_found=False
        )
        if not document:
            self.skipTest("l10n_br_nfse_nacional demo data is not installed")
        xml = document._serialize([])[0].to_xml()
        raw = Dps.schema_validation(xml, schema_path=nfse_nacional_schema_path())
        self.assertEqual(len(raw), 1)
        self.assertIn("serie", raw[0])
        self.assertEqual(document._nfse10_schema_errors(xml), [])
