# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from lxml import etree

from odoo.tests import TransactionCase, tagged

NS = {"nfe": "http://www.portalfiscal.inf.br/nfe"}


@tagged("post_install", "-at_install")
class TestPartnerDocument(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env["res.partner"].create(
            {
                "name": "Cliente Ltda",
                "is_company": True,
                "vat": "07.882.356/0001-45",
                "country_id": cls.env.ref("base.br").id,
            }
        )
        cls.contact = cls.env["res.partner"].create(
            {
                "name": "Comprador",
                "parent_id": cls.company.id,
                "type": "invoice",
                "vat": "07882356000145",
                "country_id": cls.env.ref("base.br").id,
            }
        )

    def test_company_contact_is_sent_as_cnpj(self):
        contact = self.contact
        self.assertFalse(contact.is_company)
        self.assertEqual(contact.cnpj_cpf_stripped, "07882356000145")
        for choice in (
            "nfe40_choice_dest",
            "nfe40_choice_tlocal",
            "nfe40_choice_emit",
            "nfe40_choice_transporta",
        ):
            self.assertEqual(contact[choice], "nfe40_CNPJ", choice)
        self.assertEqual(contact.nfe40_CNPJ, "07882356000145")
        self.assertFalse(contact.nfe40_CPF)

    def test_person_keeps_cpf(self):
        person = self.env["res.partner"].create(
            {
                "name": "Pessoa",
                "vat": "529.982.247-25",
                "country_id": self.env.ref("base.br").id,
            }
        )
        self.assertEqual(person.nfe40_choice_dest, "nfe40_CPF")
        self.assertEqual(person.nfe40_CPF, "52998224725")
        self.assertFalse(person.nfe40_CNPJ)

    def test_foreign_partner_untouched(self):
        foreign = self.env["res.partner"].create(
            {
                "name": "Foreign",
                "vat": "12345678901234",
                "country_id": self.env.ref("base.us").id,
            }
        )
        self.assertEqual(foreign.nfe40_choice_dest, "nfe40_idEstrangeiro")

    def test_dest_serialized_as_cnpj(self):
        """The dest group of the XML carries CNPJ, not CPF."""
        nfe = self.env.ref("l10n_br_nfe.demo_nfe_natural_icms_7_resale")
        nfe.partner_id = self.contact
        root = etree.fromstring(nfe.serialize()[0].to_xml().encode())
        dest = root.find("nfe:infNFe/nfe:dest", NS)
        self.assertEqual(dest.findtext("nfe:CNPJ", namespaces=NS), "07882356000145")
        self.assertIsNone(dest.find("nfe:CPF", NS))
