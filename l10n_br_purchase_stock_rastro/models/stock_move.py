# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime, time

from odoo import _, models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _nfe_rastro_lines(self):
        """Lines of imported documents that have this move as origin and
        carry the rastro group of the NF-e."""
        self.ensure_one()
        return self.env["l10n_br_fiscal.document.line"].search(
            [("import_stock_move_id", "=", self.id), ("nfe40_rastro", "!=", False)]
        )

    def _find_or_create_nfe_lot(self, rastro):
        self.ensure_one()
        Lot = self.env["stock.lot"]
        lot = Lot.search(
            [
                ("name", "=", rastro.nfe40_nLote),
                ("product_id", "=", self.product_id.id),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
        )
        if lot:
            return lot
        vals = {
            "name": rastro.nfe40_nLote,
            "product_id": self.product_id.id,
            "company_id": self.company_id.id,
        }
        if rastro.nfe40_dVal:
            vals["expiration_date"] = datetime.combine(rastro.nfe40_dVal, time.min)
        if rastro.nfe40_dFab and "production_date" in Lot._fields:
            vals["production_date"] = datetime.combine(rastro.nfe40_dFab, time.min)
        return Lot.create(vals)

    def _propose_lots_from_nfe(self):
        """Fill the receipt move with the lots of the NF-e (lot number, quantity
        and expiry date), for the operator to review. Nothing is validated.

        Returns the reason why nothing was proposed, or an empty string.
        """
        self.ensure_one()
        if self.state in ("done", "cancel"):
            return _("The receipt move is already closed.")
        if self.product_id.tracking != "lot":
            return _("%s is not tracked by lot.", self.product_id.display_name)
        if any(
            line.lot_id or line.lot_name or line.qty_done for line in self.move_line_ids
        ):
            return _(
                "The receipt of %s already has lots or quantities.",
                self.product_id.display_name,
            )
        document_lines = self._nfe_rastro_lines()
        if not document_lines:
            return _("The NF-e has no lot group for %s.", self.product_id.display_name)
        self.move_line_ids.unlink()
        MoveLine = self.env["stock.move.line"]
        for document_line in document_lines:
            for rastro in document_line.nfe40_rastro:
                if not rastro.nfe40_nLote:
                    continue
                quantity = document_line.uom_id._compute_quantity(
                    rastro.nfe40_qLote, self.product_uom
                )
                lot = self._find_or_create_nfe_lot(rastro)
                vals = self._prepare_move_line_vals(quantity=quantity)
                vals.update({"lot_id": lot.id, "qty_done": quantity})
                MoveLine.create(vals)
        return ""
