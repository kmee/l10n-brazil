# Copyright 2026 - TODAY, KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _create_repair_sale_order_line(self):
        """Compute the fiscal taxes of the sale order lines created for the
        repair parts.

        l10n_br_stock_account creates the stock moves with the context
        skip_compute_fiscal_tax_ids, to avoid computing taxes on the move. The
        repair part move creates its sale order line inside that same create,
        so the line inherited the context and was left without CFOP and taxes
        (the invoice then failed with "no ICMS CST")."""
        return super(
            StockMove, self.with_context(skip_compute_fiscal_tax_ids=False)
        )._create_repair_sale_order_line()

    def _prepare_repair_so_line_vals(self):
        """Sale order lines created for the repair parts get the fiscal
        operation, so CFOP and taxes are computed by l10n_br_sale."""
        vals = super()._prepare_repair_so_line_vals()
        operation = (
            self.repair_id.sale_order_id.fiscal_operation_id
            or self.repair_id.fiscal_operation_id
        )
        if operation:
            vals["fiscal_operation_id"] = operation.id
        return vals
