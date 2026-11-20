# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo import models

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    FISCAL_IN,
    PROFIT_CALCULATION_REAL,
    TAX_FRAMEWORK_SIMPLES_ALL,
)


class FiscalDocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    def _get_sped_credit_accounts(self):
        """The analytic account (COD_CTA of the C170, 0500) of the lines that the
        PVA asks it for: in a company of the non-cumulative regime, the C170 of
        a sale taxed by PIS or COFINS (CST 01 to 09), of an entry with credit
        (CST 50 to 66) and of an entry without credit (CST 70 to 75). The account
        is the one of the line of the bill; a line without a bill gives none, and
        the C170 then goes out with a blank COD_CTA, which the PVA refuses. The
        Lucro Presumido keeps it blank, which the PVA validates."""
        accounts = self.env["account.account"]
        for line in self:
            if line._sped_needs_account():
                accounts |= line.account_line_ids[:1].account_id
        return accounts

    def _sped_needs_account(self):
        self.ensure_one()
        company = self.company_id
        if (
            company.profit_calculation != PROFIT_CALCULATION_REAL
            or company.tax_framework in TAX_FRAMEWORK_SIMPLES_ALL
        ):
            return False
        if self.fiscal_operation_type == FISCAL_IN:
            codes = (self.entry_pis_cst_id.code, self.entry_cofins_cst_id.code)
        else:
            codes = (self.pis_cst_code, self.cofins_cst_code)
        return any(
            "01" <= (code or "") <= "09"
            or "50" <= (code or "") <= "66"
            or "70" <= (code or "") <= "75"
            for code in codes
        )
