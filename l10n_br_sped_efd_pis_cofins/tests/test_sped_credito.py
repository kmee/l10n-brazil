# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from datetime import date, datetime

from odoo.exceptions import UserError
from odoo.tests.common import tagged

from odoo.addons.l10n_br_tax_assessment.tests.common_entrada import SpedEntradaCommon

from .test_sped_entrada import SpedPisCofinsEntradaMixin


class CreditMixin(SpedPisCofinsEntradaMixin):
    """Entries and a sale posted by the normal path, and the PIS/COFINS
    assessment of the month, for the EFD Contribuicoes."""

    @staticmethod
    def _number(text):
        return float(text.replace(",", ".") or 0)

    def _entry(self, operation_line, number):
        """A posted supplier bill whose fiscal document the import left."""
        bill = self._purchase_move(operation_line, number)
        bill.fiscal_document_id.imported_document = True
        return bill

    def _sale(self):
        ref = self.env.ref
        sale = self.init_invoice(
            "out_invoice",
            partner=self.partner_a,
            invoice_date=date(2026, 7, 12),
            products=[self.product_a],
            document_type=ref("l10n_br_fiscal.document_55"),
            fiscal_operation=ref("l10n_br_fiscal.fo_venda"),
            fiscal_operation_lines=[ref("l10n_br_fiscal.fo_venda_venda")],
            document_serie_id=self.empresa_lc_document_55_serie_1,
        )
        sale.action_post()
        # the fiscal document of a posted sale takes the day of the posting
        when = datetime(2026, 7, 12, 12, 0)
        self.env.cr.execute(
            "UPDATE l10n_br_fiscal_document SET document_date = %s, date_in_out = %s"
            " WHERE id = %s",
            (when, when, sale.fiscal_document_id.id),
        )
        sale.fiscal_document_id.invalidate_recordset(["document_date", "date_in_out"])
        number = sale.fiscal_document_id.document_number
        sale.fiscal_document_id.write(
            {
                "state_edoc": "autorizada",
                "document_key": self._access_key(str(number), "11222333000181"),
            }
        )
        return sale

    def _assess(self, tax_domain, regime="non_cumulative"):
        """The assessment by the normal path: compute from the ledger, post."""
        group = self.env["account.tax.group"].search(
            [
                (
                    "fiscal_tax_group_id",
                    "=",
                    self.env.ref(f"l10n_br_fiscal.tax_group_{tax_domain}").id,
                )
            ],
            limit=1,
        )
        group.regime = regime
        accounts = {
            "property_tax_payable_account_id": ("PAY", "liability_current"),
            "property_tax_receivable_account_id": ("REC", "asset_current"),
        }
        group.with_company(self.company).write(
            {
                field: self.env["account.account"]
                .create(
                    {
                        "name": f"{tax_domain} {code}",
                        "code": f"{tax_domain.upper()}{code}",
                        "account_type": account_type,
                        "company_id": self.company.id,
                    }
                )
                .id
                for field, (code, account_type) in accounts.items()
            }
        )
        assessment = self.env["l10n_br_tax.assessment"].create(
            {
                "company_id": self.company.id,
                "tax_group_id": group.id,
                "date_from": "2026-07-01",
                "date_to": "2026-07-31",
            }
        )
        assessment.action_compute()
        assessment.action_post()
        return assessment

    def _month_with_credit(self):
        """A resale and an industrialization (credit), a use and consumption and a
        fixed asset (no credit), and a sale."""
        self._entry("fo_compras_compras_comercializacao", "401")
        self._entry("fo_compras_compras", "402")
        self._entry("fo_compras_compras_uso_consumo", "403")
        self._entry("fo_compras_compras_ativo", "404")
        self._sale()
        return self._assess("pis"), self._assess("cofins")


@tagged("post_install", "-at_install")
class TestSpedPisCofinsCredit(CreditMixin, SpedEntradaCommon):
    """The PIS/COFINS credit of the non-cumulative regime in the EFD
    Contribuicoes of a Lucro Real company."""

    profit_calculation = "real"

    def test_the_company_of_the_fixture_pays_the_basic_rates(self):
        """The non-cumulative regime has PIS 1.65% and COFINS 7.6%: the
        fixture of the non-cumulative company does not use the cumulative
        0.65% and 3% of the shared common of the account tests."""
        bill = self._purchase_move("fo_compras_compras_comercializacao", "401")
        line = bill.fiscal_document_id.fiscal_line_ids
        self.assertAlmostEqual(line.pis_percent, 1.65)
        self.assertAlmostEqual(line.cofins_percent, 7.6)
