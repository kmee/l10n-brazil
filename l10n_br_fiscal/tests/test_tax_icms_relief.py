# Copyright 2026 Akretion - Renato Lima <renato.lima@akretion.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import TransactionCase


class TestTaxIcmsRelief(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.nfe_tax_benefit = cls.env.ref("l10n_br_fiscal.demo_nfe_tax_benefit")
        cls.icms_relief = cls.env.ref("l10n_br_fiscal.icms_relief_9")
        cls.tax_benefit = cls.env["l10n_br_fiscal.tax.definition"].create(
            {
                "icms_regulation_id": cls.env.ref(
                    "l10n_br_fiscal.tax_icms_regulation"
                ).id,
                "tax_group_id": cls.env.ref("l10n_br_fiscal.tax_group_icms").id,
                "code": "SP810002",
                "name": "TAX BENEFIT DEMO RELIEF",
                "description": "TAX BENEFIT DEMO RELIEF",
                "benefit_type": "1",
                "is_benefit": True,
                "is_taxed": True,
                "is_debit_credit": True,
                "custom_tax": True,
                "icms_relief_id": cls.icms_relief.id,
                "tax_id": cls.env.ref("l10n_br_fiscal.tax_icms_12_red_26_57").id,
                "cst_id": cls.env.ref("l10n_br_fiscal.cst_icms_20").id,
                "state_from_id": cls.env.ref("base.state_br_sp").id,
                "state_to_ids": [Command.set(cls.env.ref("base.state_br_mg").ids)],
                "ncms": "73269090",
                "ncm_ids": [
                    Command.set(cls.env.ref("l10n_br_fiscal.ncm_73269090").ids)
                ],
                "state": "approved",
            }
        )
        # force update
        cls.nfe_tax_benefit.fiscal_line_ids._compute_fiscal_tax_ids()

    def test_nfe_tax_icms_relief(self):
        """Test NFe document line gets icms_relief_id from the tax benefit."""
        for line in self.nfe_tax_benefit.fiscal_line_ids:
            self.assertEqual(
                line.icms_tax_benefit_id,
                self.tax_benefit,
                "Document line must have tax benefit",
            )
            self.assertEqual(
                line.icms_relief_id,
                self.icms_relief,
                "Document line must have ICMS relief",
            )

    def test_new_line_gets_relief_type_from_benefit(self):
        self.tax_benefit.icms_relief_type = "1"
        line = self.env["l10n_br_fiscal.document.line"].create(
            {
                "document_id": self.nfe_tax_benefit.id,
                "name": "Teste",
                "product_id": self.env.ref("product.product_product_7").id,
                "uom_id": self.env.ref("uom.product_uom_unit").id,
                "quantity": 1,
                "fiscal_operation_type": "out",
                "fiscal_operation_id": self.env.ref("l10n_br_fiscal.fo_venda").id,
                "fiscal_operation_line_id": self.env.ref(
                    "l10n_br_fiscal.fo_venda_venda_nao_contribuinte"
                ).id,
            }
        )
        self.assertEqual(line.icms_relief_id, self.icms_relief)
        self.assertEqual(line.icms_relief_type, "1")

    def test_benefit_without_relief_keeps_line_relief(self):
        line = self.nfe_tax_benefit.fiscal_line_ids
        line.icms_relief_type = "1"
        self.tax_benefit.icms_relief_id = False
        line._compute_fiscal_tax_ids()
        self.assertEqual(line.icms_relief_id, self.icms_relief)
        self.assertEqual(line.icms_relief_type, "1")

    def test_exempt_cst_relief_uses_standard_rate(self):
        self.tax_benefit.write(
            {
                "tax_id": self.env.ref("l10n_br_fiscal.tax_icms_isento").id,
                "cst_id": self.env.ref("l10n_br_fiscal.cst_icms_40").id,
            }
        )
        line = self.nfe_tax_benefit.fiscal_line_ids
        line.write({"price_unit": 1000.0, "quantity": 1.0})
        line._compute_fiscal_tax_ids()
        # ICMS 12% from SP to MG without the benefit
        self.assertEqual(line.icms_relief_value, 120.0)
        self.assertEqual(self.nfe_tax_benefit.amount_icms_relief_value, 120.0)
