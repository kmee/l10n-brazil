# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo import models

from odoo.addons.l10n_br_fiscal.constants.fiscal import FISCAL_IN


class FiscalDocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    def _sped_icms_without_credit(self):
        """An entry line whose ICMS the company does not credit (use and
        consumption, fixed asset, supplier of the Simples Nacional, company of the
        Simples): the books carry it as the Guia asks for an entry without
        credit right, CST of the origin plus 90 and no base, rate or value of
        ICMS, so the C100 and the C190 sum what the E110 credits.

        The verdict is the one the ledger uses (``_get_stock_cost_tax_map``): a
        line without a destination keeps the historic behaviour, credit.
        """
        self.ensure_one()
        if self.fiscal_operation_type != FISCAL_IN or not self.product_destination:
            return False
        return self._get_stock_cost_tax_map().get("icms") == "cost"
