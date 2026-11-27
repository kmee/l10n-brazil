# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _import_document_lines(self):
        """Lines of imported documents that point to this receipt move."""
        self.ensure_one()
        return (
            self.env["l10n_br_fiscal.document.line"]
            .sudo()
            .search([("import_stock_move_id", "=", self.id)])
        )

    def _propose_from_import(self):
        """Propose, on the receipt moves, the quantity the document declares.

        A receipt arrives with the ordered quantity; the document says what
        really came. Only a move that is open and was not picked by the operator
        receives it, so what the operator already did is kept, and nothing is
        validated.
        """
        for move in self:
            lines = move._import_document_lines()
            if not lines or move.picked or move.state in ("done", "cancel", "draft"):
                continue
            move.quantity = sum(
                line.uom_id._compute_quantity(
                    line.quantity, move.product_uom, raise_if_failure=False
                )
                if line.uom_id
                else line.quantity
                for line in lines
            )
