# Copyright 2026 KMEE INFORMATICA LTDA - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

from odoo.addons.l10n_br_fiscal.constants.fiscal import TAX_FRAMEWORK_SIMPLES_ALL

# Tax domains whose input credit can be derived from the line CST plus the
# buyer company tax regime.
CREDITABLE_TAX_DOMAINS = ("icms", "ipi", "pis", "cofins")

# CFOP destinations that take no input credit on the acquisition: own use
# and consumption (LC 87/96, art. 33, I) and fixed assets, whose ICMS (CIAP)
# and PIS/COFINS credits are spread over 48 months, which is not implemented,
# so the tax stays in the cost.
RESTRICTED_DESTINATIONS = ("purchase_ownuse", "purchase_asset")

# CSTs that give the right to an input credit, per tax domain. The 16.0 net
# cost stack stores this as ``l10n_br_fiscal.cst.default_creditable_tax``;
# that field does not exist in 18.0, so the list is kept here.
_PISCOFINS_CREDIT_CSTS = tuple(str(code) for code in [*range(50, 57), *range(60, 68)])
CREDITABLE_CST_CODES = {
    # ICMS 00, 10, 20, 70 and CSOSN with credit permission 101, 201.
    "icms": ("00", "10", "20", "70", "101", "201"),
    # IPI 00: entry with credit recovery.
    "ipi": ("00",),
    # PIS/COFINS: right to credit (50-56) and presumed credit (60-67).
    "pis": _PISCOFINS_CREDIT_CSTS,
    "cofins": _PISCOFINS_CREDIT_CSTS,
}


class FiscalDocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    landed_cost_amount = fields.Monetary(
        compute="_compute_landed_cost_amount",
        help="Amount of this line that the landed cost allocates to the"
        " receipts: the net acquisition cost when the company allocates"
        " landed costs at net cost and the line states its fiscal operation,"
        " the gross amount otherwise.",
    )

    @api.depends(
        "fiscal_amount_total",
        "amount_tax_withholding",
        "fiscal_tax_ids",
        "icms_value",
        "ipi_value",
        "pis_value",
        "cofins_value",
        "icms_cst_id",
        "ipi_cst_id",
        "pis_cst_id",
        "cofins_cst_id",
        "icmssn_credit_value",
        "cfop_id",
        "fiscal_operation_line_id",
        "company_id.landed_cost_net_cost",
        "document_id.landed_cost_picking_ids",
    )
    def _compute_landed_cost_amount(self):
        for record in self:
            record.landed_cost_amount = record._get_landed_cost_amount()

    # ------------------------------------------------------------------
    # Creditability: minimal port of l10n_br_fiscal.stock.price.mixin from
    # the 16.0 net cost stack (OCA #4965-#4970), local to this module.
    # ------------------------------------------------------------------

    def _is_non_cumulative(self):
        """Whether the company is under the non-cumulative PIS/COFINS regime.

        Falls back to the profit calculation when the regime was never set.
        """
        self.ensure_one()
        regime = self.company_id.piscofins_id
        if not regime:
            return self.company_id.profit_calculation == "real"
        non_cumulative = self.env.ref(
            "l10n_br_fiscal.tax_pis_cofins_nao_columativo", raise_if_not_found=False
        )
        return bool(non_cumulative) and regime == non_cumulative

    def _creditable_tax_regime_gates(self):
        """Which tax domains the BUYER company may credit, by tax regime.

        - Simples Nacional takes no credit (LC 123/2006, art. 23);
        - IPI only by industries and assimilated (RIPI, arts. 226 and 251);
        - PIS/COFINS only in the non-cumulative regime (Leis 10.637/2002 and
          10.833/2003, art. 3).
        """
        self.ensure_one()
        company = self.company_id
        simples = company.tax_framework in TAX_FRAMEWORK_SIMPLES_ALL
        industry = company.is_industry or company.ripi
        non_cumulative = self._is_non_cumulative()
        return {
            "icms": not simples,
            "ipi": not simples and industry,
            "pis": not simples and non_cumulative,
            "cofins": not simples and non_cumulative,
        }

    def _landed_cost_target_moves(self):
        self.ensure_one()
        return self.document_id.landed_cost_picking_ids.move_ids.filtered(
            lambda move: move.state != "cancel"
        )

    def _creditable_tax_destination_gates(self):
        """Which tax domains the DESTINATION of the goods vetoes.

        A freight or expense takes the destination of the goods it lands on.
        The CFOP of a transport service (1351 to 1356) states who bought the
        service, not where the goods go, so on its own it never vetoes a
        credit. Each receipt the cost is allocated to does state it, and a tax
        the goods cannot recover is not recoverable on their freight either.
        A receipt whose destination is unknown (no CFOP) keeps every tax in
        the cost.
        """
        self.ensure_one()
        vetoed = dict.fromkeys(CREDITABLE_TAX_DOMAINS, False)
        if self.cfop_id.type_move in RESTRICTED_DESTINATIONS:
            return vetoed
        moves = self._landed_cost_target_moves()
        if any(
            not move.cfop_id or move.cfop_id.type_move in RESTRICTED_DESTINATIONS
            for move in moves
        ):
            return vetoed
        return {}

    def _is_simples_supplier_without_credit(self):
        """Simples supplier that transferred no ICMS credit on the document.

        Only ICMS is affected: PIS/COFINS credits of a non-cumulative buyer do
        not depend on the supplier regime (ADI SRF 15/2007).
        """
        self.ensure_one()
        partner = self.partner_id or self.document_id.partner_id
        if not partner or partner.tax_framework not in TAX_FRAMEWORK_SIMPLES_ALL:
            return False
        return not self.icmssn_credit_value

    def _is_landed_cost_tax_creditable(self, tax_domain):
        """Whether this line may credit ``tax_domain``.

        Three independent gates, all of which must allow the credit: the buyer
        regime, the destination of the goods and the nature of the operation
        (the line CST).
        """
        self.ensure_one()
        if tax_domain not in CREDITABLE_TAX_DOMAINS:
            return False
        if not self._creditable_tax_regime_gates().get(tax_domain):
            return False
        if self._creditable_tax_destination_gates().get(tax_domain) is False:
            return False
        if tax_domain == "icms" and self._is_simples_supplier_without_credit():
            return False
        cst = self[f"{tax_domain}_cst_id"]
        return bool(cst) and cst.code in CREDITABLE_CST_CODES[tax_domain]

    def _get_landed_cost_creditable_domains(self):
        self.ensure_one()
        return tuple(
            domain
            for domain in CREDITABLE_TAX_DOMAINS
            if self._is_landed_cost_tax_creditable(domain)
        )

    def _get_landed_cost_amount(self):
        """Amount of this line that goes into the stock as a landed cost.

        The net acquisition cost when the company allocates landed costs at
        net cost and the line states its fiscal operation, so the
        creditability can be derived. Otherwise the gross amount.

        Withholdings are added back: _compute_fiscal_amounts deducts them from
        fiscal_amount_total, but a withholding is a financial obligation of
        the buyer, not a reduction of what was acquired (CPC 16, item 11).
        """
        self.ensure_one()
        amount = self.fiscal_amount_total + self.amount_tax_withholding
        if self.company_id.landed_cost_net_cost and self.fiscal_operation_line_id:
            creditable = self._get_landed_cost_creditable_domains()
            for tax in self.fiscal_tax_ids:
                if tax.tax_domain in creditable:
                    amount -= self[f"{tax.tax_domain}_value"]
        return self.company_id.currency_id.round(amount)
