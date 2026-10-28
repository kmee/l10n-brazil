# Copyright 2026 KMEE INFORMATICA LTDA - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models

from odoo.addons.l10n_br_fiscal.models.stock_price_mixin import (
    CREDITABLE_TAX_DOMAINS,
)


class FiscalDocumentLine(models.Model):
    _name = "l10n_br_fiscal.document.line"
    _inherit = [_name, "l10n_br_fiscal.stock.price.mixin"]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            # A journal item without fiscal line copies it as False (_inherits),
            # on a reversal for instance: let the default apply.
            if "creditability_origin" in vals and not vals["creditability_origin"]:
                del vals["creditability_origin"]
        return super().create(vals_list)

    def _get_cost_unit_qty(self):
        self.ensure_one()
        return self.quantity

    @api.depends(
        "document_id.landed_cost_picking_ids",
        "document_id.landed_cost_picking_ids.move_ids.cfop_id",
    )
    def _compute_taxes_creditable(self):
        return super()._compute_taxes_creditable()

    def _landed_cost_target_moves(self):
        self.ensure_one()
        return self.document_id.landed_cost_picking_ids.move_ids.filtered(
            lambda move: move.state != "cancel"
        )

    def _creditable_tax_destination_gates(self):
        """A freight or expense takes the destination of the goods it lands on.

        The CFOP of a transport service (1351 to 1356) states who bought the
        service, not where the goods go, so on its own it never vetoes a
        credit. Each receipt the cost is allocated to does state it, and a
        tax that the goods cannot recover is not recoverable on their
        freight either. A receipt whose destination is unknown (no CFOP)
        keeps every tax in the cost.
        """
        gates = super()._creditable_tax_destination_gates()
        moves = self._landed_cost_target_moves()
        if not moves:
            return gates
        if any(not move.cfop_id for move in moves):
            return dict.fromkeys(CREDITABLE_TAX_DOMAINS, False)
        gates = dict(gates)
        for move in moves:
            for domain, allowed in move._creditable_tax_destination_gates().items():
                if not allowed:
                    gates[domain] = False
        return gates

    def _get_landed_cost_amount(self):
        """Amount of this line that goes into the stock as a landed cost.

        The net acquisition cost when the company values its stock net of
        recoverable taxes and the line states its fiscal operation, so the
        creditability can be derived. Otherwise the gross amount, the same
        the goods themselves would be valued at.
        """
        self.ensure_one()
        if self.valuation_via_stock_price and self.fiscal_operation_line_id:
            amount = self.cost_unit * self.quantity
        else:
            amount = self.fiscal_amount_total + self.amount_tax_withholding
        return self.company_id.currency_id.round(amount)
