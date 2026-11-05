# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import Form, TransactionCase


class VatFormattedEditableTest(TransactionCase):
    """The CNPJ/CPF typed in the partner form must end up in the vat field."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.brazil = cls.env.ref("base.br")

    def test_form_vat_formatted_is_stored_in_vat(self):
        with Form(self.env["res.partner"]) as form:
            form.name = "Vat Formatted Form Test"
            form.country_id = self.brazil
            form.vat_formatted_cnpj = "11.222.333/0001-81"
        partner = form.save()
        self.assertEqual(partner.vat, "11222333000181")
        self.assertEqual(partner.vat_formatted_cnpj, "11.222.333/0001-81")

    def test_form_vat_formatted_cpf(self):
        with Form(self.env["res.partner"]) as form:
            form.name = "Vat Formatted CPF Test"
            form.country_id = self.brazil
            form.vat_formatted_cnpj = "529.982.247-25"
        partner = form.save()
        self.assertEqual(partner.vat, "52998224725")

    def test_form_vat_formatted_cleared(self):
        partner = self.env["res.partner"].create(
            {"name": "Vat Clear Test", "country_id": self.brazil.id}
        )
        partner.vat = "52998224725"
        with Form(partner) as form:
            form.vat_formatted_cnpj = False
        self.assertFalse(partner.vat)

    def test_write_vat_formatted(self):
        partner = self.env["res.partner"].create(
            {"name": "Vat Write Test", "country_id": self.brazil.id}
        )
        partner.write({"vat_formatted_cnpj": "529.982.247-25"})
        self.assertEqual(partner.vat, "52998224725")
