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

    def _sped_ipi_without_credit(self):
        """An entry line whose IPI the company does not credit (only the
        industrialization of an industrial company does): the IPI stays in the
        cost, and the books carry CST 49 (other entries) and no base, rate or
        value of IPI, so the C190, the C100 and the E510 sum what the E520
        credits. Same verdict as the ledger."""
        self.ensure_one()
        if self.fiscal_operation_type != FISCAL_IN or not self.product_destination:
            return False
        return self._get_stock_cost_tax_map().get("ipi") == "cost"

    def _get_sped_icms_values(self):
        """The ICMS of the line as the C170 carries it, in every declaration that
        has the register (EFD ICMS/IPI and EFD Contribuicoes): the CST (origin
        plus the 2 digits), the base, the rate and the value. An entry without
        credit right is CST of the origin plus 90 and no base, rate or value; the
        other lines keep the ones of the document."""
        self.ensure_one()
        origin = self.icms_origin or "0"
        if self._sped_icms_without_credit():
            return {
                "cst": f"{origin}90",
                "base": 0.0,
                "percent": 0.0,
                "value": 0.0,
            }
        return {
            "cst": f"{origin}{self.icms_cst_code or '00'}",
            "base": self.icms_base,
            "percent": self.icms_percent,
            "value": self.icms_value,
        }

    def _get_sped_ipi_values(self):
        """The IPI of the line as the C170 carries it: the CST, the base, the rate
        and the value. An entry without credit right is CST 49 (other entries)
        and no base, rate or value."""
        self.ensure_one()
        if self._sped_ipi_without_credit():
            return {"cst": "49", "base": 0.0, "percent": 0.0, "value": 0.0}
        return {
            "cst": self.entry_ipi_cst_id.code or self.ipi_cst_code,
            "base": self.ipi_base,
            "percent": self.ipi_percent,
            "value": self.ipi_value,
        }
