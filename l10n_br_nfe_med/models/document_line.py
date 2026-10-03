# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    EDOC_PURPOSE_AJUSTE,
    EDOC_PURPOSE_COMPLEMENTAR,
    EDOC_PURPOSE_DEVOLUCAO,
)

# Rule K01-20 (rejection 873) exceptions, NT 2021.004 v1.34 and
# NT 2026.002 v1.11: future delivery and sale on behalf of a third party
K01_20_CFOP_EXCEPTIONS = (
    "5922",
    "6922",
    "5118",
    "6118",
    "5119",
    "6119",
    "5120",
    "6120",
)


class FiscalDocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    nfe40_med = fields.Many2one(
        compute="_compute_nfe40_med",
        store=True,
        readonly=False,
    )

    @api.depends("product_id")
    def _compute_nfe40_med(self):
        for line in self:
            line.nfe40_med = line.product_id.nfe40_med

    def _nfe40_rastro_is_required(self):
        """Rule K01-20 (rejection 873): an item with the medicine group
        must carry the traceability group, except in the cases listed by
        the rule."""
        if super()._nfe40_rastro_is_required():
            return True
        if not self.nfe40_med:
            return False
        document = self.document_id
        return not (
            document.edoc_purpose
            in (EDOC_PURPOSE_COMPLEMENTAR, EDOC_PURPOSE_AJUSTE, EDOC_PURPOSE_DEVOLUCAO)
            or document.ind_pres in ("2", "3")
            or document.nfe40_tpNF == "0"
            or document.nfe40_tpImp == "6"
            or self.cfop_id.code in K01_20_CFOP_EXCEPTIONS
        )
