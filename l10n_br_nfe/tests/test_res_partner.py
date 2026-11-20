# Copyright 2023 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest import mock

from odoo.tests import TransactionCase


class TestNFCeResPartner(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_id = cls.env.ref("l10n_br_base.res_partner_kmee")
        cls.partner_id.is_anonymous_consumer = True

    def test_compute_fields(self):
        self.partner_id._compute_nfe40_ender()

        self.assertFalse(self.partner_id.nfe40_xLgr)
        self.assertFalse(self.partner_id.nfe40_nro)
        self.assertFalse(self.partner_id.nfe40_xCpl)
        self.assertFalse(self.partner_id.nfe40_xBairro)
        self.assertFalse(self.partner_id.nfe40_cMun)
        self.assertFalse(self.partner_id.nfe40_xMun)
        self.assertFalse(self.partner_id.nfe40_UF)
        self.assertFalse(self.partner_id.nfe40_cPais)
        self.assertFalse(self.partner_id.nfe40_xPais)


class TestAnonymousConsumerData(TransactionCase):
    def test_anonymous_consumer_data(self):
        """The standard anonymous consumer comes marked."""
        partner = self.env.ref("l10n_br_fiscal.res_partner_anonimo")
        self.assertTrue(partner.is_anonymous_consumer)


class TestMatchOfAnotherSchema(TransactionCase):
    """The matching of the NF-e answers only for the NF-e: a dictionary of another
    schema goes to the next override of the chain, whatever modules are installed
    (the CT-e is loaded before this module and its dictionaries used to end here,
    which created a partner with no name)."""

    def _next_in_chain(self, partner):
        chain = type(partner).__mro__
        mine = next(
            index
            for index, cls in enumerate(chain)
            if cls.__module__ == "odoo.addons.l10n_br_nfe.models.res_partner"
            and "match_or_create_m2o" in cls.__dict__
        )
        return next(
            cls for cls in chain[mine + 1 :] if "match_or_create_m2o" in cls.__dict__
        )

    def test_the_partner_of_another_schema_is_matched_by_the_next_in_the_chain(self):
        calls = []

        def following(model, rec_dict, parent_dict, model_=None):
            calls.append((rec_dict, parent_dict))
            return 42

        partner = self.env["res.partner"].with_context(spec_schema="xyz")
        with mock.patch.object(
            self._next_in_chain(partner), "match_or_create_m2o", following
        ):
            result = partner.match_or_create_m2o(
                {"xyz40_CNPJ": "1"}, {"nfe40_CNPJ": "2"}
            )

        self.assertEqual(result, 42)
        self.assertEqual(calls, [({"xyz40_CNPJ": "1"}, {"nfe40_CNPJ": "2"})])
