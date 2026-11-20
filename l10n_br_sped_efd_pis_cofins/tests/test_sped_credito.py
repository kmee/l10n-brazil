# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

import calendar
from datetime import date, datetime

from odoo.tests.common import tagged

from odoo.addons.l10n_br_tax_assessment.tests.common_entrada import SpedEntradaCommon

from .test_sped_entrada import SpedPisCofinsEntradaMixin


class CreditMixin(SpedPisCofinsEntradaMixin):
    """Entries and a sale posted by the normal path, and the PIS/COFINS
    assessment of the month, for the EFD Contribuicoes."""

    @staticmethod
    def _number(text):
        return float(text.replace(",", ".") or 0)

    def _set_accountant(self):
        city = self.env["res.city"].search([("state_id.code", "=", "SP")], limit=1)
        self.company.accountant_id = self.env["res.partner"].create(
            {
                "name": "Accountant",
                "is_accountant": True,
                "cnpj_cpf": "111.444.777-35",
                "crc_code": "1SP123456/O-0",
                "email": "accountant@example.com",
                "country_id": self.env.ref("base.br").id,
                "state_id": self.env.ref("base.state_br_sp").id,
                "city_id": city.id,
            }
        )

    def _entry(self, operation_line, number, invoice_date=None):
        """A posted supplier bill whose fiscal document the import left."""
        bill = self._purchase_move(operation_line, number, invoice_date=invoice_date)
        bill.fiscal_document_id.imported_document = True
        return bill

    def _sale(self, day=date(2026, 7, 12)):
        ref = self.env.ref
        sale = self.init_invoice(
            "out_invoice",
            partner=self.partner_a,
            invoice_date=day,
            products=[self.product_a],
            document_type=ref("l10n_br_fiscal.document_55"),
            fiscal_operation=ref("l10n_br_fiscal.fo_venda"),
            fiscal_operation_lines=[ref("l10n_br_fiscal.fo_venda_venda")],
            document_serie_id=self.empresa_lc_document_55_serie_1,
        )
        sale.action_post()
        # the fiscal document of a posted sale takes the day of the posting
        when = datetime(day.year, day.month, day.day, 12, 0)
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

    def _assess(self, tax_domain, regime="non_cumulative", month=7, post=True):
        """The assessment of the month by the normal path: compute from the
        ledger, post."""
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
        if regime:
            group.regime = regime
        accounts = {
            "property_tax_payable_account_id": ("PAY", "liability_current"),
            "property_tax_receivable_account_id": ("REC", "asset_current"),
        }
        if not group.with_company(self.company).property_tax_payable_account_id:
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
                "date_from": date(2026, month, 1),
                "date_to": date(2026, month, calendar.monthrange(2026, month)[1]),
            }
        )
        assessment.action_compute()
        if post:
            assessment.action_post()
        return assessment


@tagged("post_install", "-at_install")
class TestSpedPisCofinsCredit(CreditMixin, SpedEntradaCommon):
    """The PIS/COFINS credit of the non-cumulative regime in the EFD
    Contribuicoes of a Lucro Real company."""

    profit_calculation = "real"

    def test_the_c170_of_a_non_cumulative_company_carries_the_account(self):
        """The PVA asks the analytic account in the C170 of the sale (CST 01) and
        of the entry with credit (CST 50) of the non-cumulative company, and the
        0500 declares each one."""
        self._entry("fo_compras_compras_comercializacao", "401")
        self._sale()
        declaration = self._declaration_july()
        c170 = self._sped_records(declaration, "C170")
        self.assertEqual({rec["CST_PIS"] for rec in c170}, {"01", "50"})
        codes = [rec["COD_CTA"] for rec in self._sped_records(declaration, "0500")]
        for rec in c170:
            self.assertTrue(rec["COD_CTA"], rec["CST_PIS"])
            self.assertIn(rec["COD_CTA"], codes)
        self.assertEqual(len(codes), len(set(codes)))


@tagged("post_install", "-at_install")
class TestSpedPisCofinsCumulativeUnchanged(CreditMixin, SpedEntradaCommon):
    """The Lucro Presumido keeps its file: no credit block, no account of the
    sale (the PVA validates it without)."""

    def test_the_cumulative_company_has_no_credit_block(self):
        self._entry("fo_compras_compras_comercializacao", "401")
        self._sale()
        self._assess("pis", regime="cumulative")
        self._assess("cofins", regime="cumulative")
        declaration = self._declaration_july()
        for register in ("M100", "M105", "M500", "M505"):
            self.assertEqual(self._sped_records(declaration, register), [], register)
        sale_line = [
            rec
            for rec in self._sped_records(declaration, "C170")
            if rec["CST_PIS"] == "01"
        ][0]
        self.assertEqual(sale_line["COD_CTA"], "")
        self.assertEqual(self._sped_records(declaration, "0500"), [])
