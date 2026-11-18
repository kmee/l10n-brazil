# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo import _, models
from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    FISCAL_IN,
)

# CST of the credit the EFD Contribuicoes understands without more data than the
# fiscal line carries (see `_sped_credit`)
CREDIT_CST = "50"
# Table 4.3.7 (nature of the base of the credit) by destination of the product:
# bens para revenda and bens utilizados como insumo
NAT_BC_CRED_BY_DESTINATION = {"resale": "01", "industrialization": "02"}
# Table 4.3.6 (type of the credit) of the CST 50
COD_CRED_BASIC = "101"
COD_CRED_DIFFERENTIATED = "102"


class FiscalDocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    def _get_sped_credit_accounts(self):
        """The analytic account (COD_CTA of the C170, 0500) of the lines of an
        entry that books a PIS/COFINS credit (CST 50 to 66): the account of the
        line of the bill. A line without a bill gives none, and the C170 then
        goes out with a blank COD_CTA, which the PVA refuses."""
        accounts = self.env["account.account"]
        for line in self:
            if line._sped_books_credit():
                accounts |= line.account_line_ids[:1].account_id
        return accounts

    def _sped_books_credit(self):
        self.ensure_one()
        return any(
            "50" <= (cst.code or "") <= "66"
            for cst in (self.entry_pis_cst_id, self.entry_cofins_cst_id)
        )

    def _sped_credit(self, tax_domain):
        """The credit this entry line books in the C170 (CST 50 to 66) for the
        M100/M105 (PIS) or M500/M505 (COFINS), or None when it books none.

        The fiscal line only has what it takes to tell the credit linked to the
        taxed revenue in the domestic market (CST 50) of a resale or an input
        (industrialization): the type of the credit is 101 at the basic rate of
        the regime and 102 at another, and the nature of the base is 01 or 02 by
        the destination. Any other CST or destination would be a guess, so the
        file is not generated and the message says which line it is."""
        self.ensure_one()
        if self.fiscal_operation_type != FISCAL_IN:
            return None
        cst = self[f"entry_{tax_domain}_cst_id"].code or ""
        if not ("50" <= cst <= "66"):
            return None
        nat_bc = NAT_BC_CRED_BY_DESTINATION.get(self.product_destination)
        if cst != CREDIT_CST or not nat_bc:
            raise UserError(
                _(
                    "The line %(line)s of the document %(document)s books the "
                    "%(tax)s credit with the CST %(cst)s and the destination "
                    "%(destination)s, which the file does not derive (only the CST "
                    "50 of a resale or of an input).",
                    line=self.name or self.id,
                    document=self.document_id.document_number or self.document_id.id,
                    tax=tax_domain.upper(),
                    cst=cst,
                    destination=self.product_destination or "",
                )
            )
        basic = self.company_id.piscofins_id[f"tax_{tax_domain}_id"].percent_amount
        rate = self[f"{tax_domain}_percent"]
        return {
            "cst": cst,
            "nat_bc": nat_bc,
            "base": self[f"{tax_domain}_base"],
            "rate": rate,
            "value": self[f"{tax_domain}_value"],
            "cod_cred": (
                COD_CRED_BASIC
                if abs(rate - basic) < 0.00005
                else COD_CRED_DIFFERENTIATED
            ),
        }
