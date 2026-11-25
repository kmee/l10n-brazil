# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCTePartnerMatch(TransactionCase):
    """Partner matching on import when l10n_br_nfe is installed too.

    Both l10n_br_nfe and l10n_br_cte override res.partner.match_or_create_m2o.
    Once the whole registry is loaded the NF-e override comes first in the MRO,
    so it has to hand the partners of another schema (``spec_schema`` in the
    context, set by ``build_from_binding``) over to the next override,
    otherwise the issuer of a CT-e is created again and the CNPJ check refuses
    it.
    Run after the install (``post_install``): while this module is loading the
    NF-e override is not in the registry yet and the defect does not show.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        modules = cls.env["ir.module.module"].search(
            [
                ("name", "in", ("l10n_br_nfe", "l10n_br_cte")),
                ("state", "=", "installed"),
            ]
        )
        cls.skip_reason = (
            False
            if len(modules) == 2
            else "l10n_br_nfe and l10n_br_cte must both be installed"
        )
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Emitente Existente",
                "vat": "87697453000105",
                "country_id": cls.env.ref("base.br").id,
                "is_company": True,
            }
        )

    def setUp(self):
        super().setUp()
        if self.skip_reason:
            self.skipTest(self.skip_reason)

    def test_cte_issuer_is_matched_by_cnpj(self):
        rec_dict = {"cte40_CNPJ": "87697453000105", "cte40_xNome": "Emitente"}
        partners = self.env["res.partner"].with_context(spec_schema="cte")
        partner_id = partners.match_or_create_m2o(rec_dict, {})
        self.assertEqual(partner_id, self.partner.id)

    def test_nfe_issuer_is_matched_by_cnpj(self):
        rec_dict = {"nfe40_CNPJ": "87697453000105", "nfe40_xNome": "Emitente"}
        partners = self.env["res.partner"].with_context(spec_schema="nfe")
        partner_id = partners.match_or_create_m2o(rec_dict, {})
        self.assertEqual(partner_id, self.partner.id)
