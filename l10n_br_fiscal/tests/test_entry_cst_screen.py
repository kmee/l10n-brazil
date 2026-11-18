# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

import json

from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestEntryCstScreen(TransactionCase):
    """The entry CSTs and the supplier benefit code have a place on the screen,
    in the language of the user."""

    FIELDS = (
        "entry_ipi_cst_id",
        "entry_pis_cst_id",
        "entry_cofins_cst_id",
        "partner_icms_tax_benefit_code",
    )

    def _form_fields(self):
        view = self.env.ref("l10n_br_fiscal.document_fiscal_line_mixin_form")
        arch = self.env["l10n_br_fiscal.document.line"].get_view(view.id)["arch"]
        return etree.fromstring(arch)

    def test_the_new_fields_are_on_the_taxes_tabs_and_read_only(self):
        form = self._form_fields()
        pages = {
            "entry_ipi_cst_id": "ipi",
            "entry_pis_cst_id": "pis",
            "entry_cofins_cst_id": "cofins",
        }
        for name, page in pages.items():
            nodes = form.xpath(f"//page[@name='{page}']//field[@name='{name}']")
            self.assertEqual(len(nodes), 1, name)
            modifiers = json.loads(nodes[0].get("modifiers"))
            self.assertTrue(modifiers.get("readonly"), name)
            self.assertTrue(modifiers.get("invisible"), "shown only when filled")
        benefit = form.xpath("//field[@name='partner_icms_tax_benefit_code']")
        self.assertEqual(len(benefit), 1)
        self.assertTrue(json.loads(benefit[0].get("modifiers")).get("readonly"))

    def test_the_new_fields_have_a_portuguese_label(self):
        self.env["res.lang"]._activate_lang("pt_BR")
        self.env["ir.module.module"].search(
            [("name", "=", "l10n_br_fiscal")]
        )._update_translations(["pt_BR"])
        fields = self.env["l10n_br_fiscal.document.line"].with_context(lang="pt_BR")
        strings = {
            name: field["string"]
            for name, field in fields.fields_get(self.FIELDS).items()
        }
        self.assertEqual(
            strings,
            {
                "entry_ipi_cst_id": "CST de Entrada do IPI (empresa)",
                "entry_pis_cst_id": "CST de Entrada do PIS (empresa)",
                "entry_cofins_cst_id": "CST de Entrada da COFINS (empresa)",
                "partner_icms_tax_benefit_code": (
                    "Código de Benefício Fiscal do Fornecedor (cBenef)"
                ),
            },
        )
