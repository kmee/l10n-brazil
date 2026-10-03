# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command, models


class AccountMoveLine(models.Model):
    _inherit = "account.move.line"

    def _prepare_nfe40_rastro_vals_list(self):
        """Traceability groups of this invoice line, one per lot of the
        stock moves it was created from, in the invoice line unit."""
        self.ensure_one()
        quantities = {}
        for move_line in self.move_line_ids.move_line_ids.filtered("lot_id"):
            quantity = move_line.product_uom_id._compute_quantity(
                move_line.quantity, self.product_uom_id
            )
            quantities[move_line.lot_id] = (
                quantities.get(move_line.lot_id, 0.0) + quantity
            )
        return [
            lot._prepare_nfe40_rastro_vals(quantity)
            for lot, quantity in quantities.items()
        ]

    def _fill_nfe40_rastro(self):
        """(Re)build the NF-e traceability groups from the stock lots."""
        for line in self.filtered("fiscal_document_line_id"):
            vals_list = line._prepare_nfe40_rastro_vals_list()
            if not vals_list:
                continue
            line.fiscal_document_line_id.nfe40_rastro = [Command.clear()] + [
                Command.create(vals) for vals in vals_list
            ]
