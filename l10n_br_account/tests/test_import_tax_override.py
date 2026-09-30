# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from types import SimpleNamespace

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestImportTaxOverride(TransactionCase):
    def test_override_taxes_from_import_repartition_factor(self):
        """compute_all returns one entry per tax repartition line: each one
        must carry only its share (factor) of the imported tax value."""
        country = self.env.ref("base.br")
        tax_group = self.env["account.tax.group"].create(
            {
                "name": "ICMS split",
                "country_id": country.id,
                "fiscal_tax_group_id": self.env.ref("l10n_br_fiscal.tax_group_icms").id,
            }
        )
        repartition = [
            Command.create({"document_type": doc_type, "repartition_type": "base"})
            for doc_type in ("invoice", "refund")
        ] + [
            Command.create(
                {
                    "document_type": doc_type,
                    "repartition_type": "tax",
                    "factor_percent": 50,
                }
            )
            for doc_type in ("invoice", "refund")
            for _half in range(2)
        ]
        tax = self.env["account.tax"].create(
            {
                "name": "ICMS 50/50",
                "amount": 18,
                "type_tax_use": "purchase",
                "country_id": country.id,
                "tax_group_id": tax_group.id,
                "repartition_line_ids": repartition,
            }
        )
        tax_lines = tax.invoice_repartition_line_ids.filtered(
            lambda line: line.repartition_type == "tax"
        )
        self.assertEqual(len(tax_lines), 2)
        taxes = [
            {"id": tax.id, "tax_repartition_line_id": line.id, "amount": 0.0}
            for line in tax_lines
        ]
        fiscal_line = SimpleNamespace(icms_value=100.0, icms_base=1000.0)
        self.env["account.move.line"]._override_taxes_from_import(taxes, fiscal_line, 1)
        self.assertEqual([vals["amount"] for vals in taxes], [50.0, 50.0])
        self.assertEqual({vals["base"] for vals in taxes}, {1000.0})
