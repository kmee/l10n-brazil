# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo import models


class FiscalDocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    def _get_sped_credit_accounts(self):
        """The analytic account (COD_CTA of the C170, 0500) of the lines of an
        entry that books a PIS/COFINS credit (CST 50 to 66): the account of the
        line of the bill. A line without a bill gives none, and the C170 then
        goes out with a blank COD_CTA, which the PVA refuses for a credit."""
        accounts = self.env["account.account"]
        for line in self:
            credit = any(
                "50" <= (cst.code or "") <= "66"
                for cst in (line.entry_pis_cst_id, line.entry_cofins_cst_id)
            )
            if credit:
                accounts |= line.account_line_ids[:1].account_id
        return accounts
