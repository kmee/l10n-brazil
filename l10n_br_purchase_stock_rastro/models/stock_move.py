# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime, time

from odoo import _, models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _nfe_rastro_lines(self):
        """Lines of imported documents that point to this receipt move, or to
        its purchase order line when no move is recorded and the order line has
        this single pending move, and carry the rastro group of the NF-e."""
        self.ensure_one()
        Line = self.env["l10n_br_fiscal.document.line"]
        domain = [("import_stock_move_id", "=", self.id)]
        if self.purchase_line_id:
            pending = self.purchase_line_id.move_ids.filtered(
                lambda move: move.state not in ("done", "cancel")
            )
            if pending == self:
                domain = [
                    "|",
                    ("import_stock_move_id", "=", self.id),
                    "&",
                    ("import_stock_move_id", "=", False),
                    ("import_purchase_line_id", "=", self.purchase_line_id.id),
                ]
        return Line.search(domain + [("nfe40_rastro", "!=", False)])

    def _nfe_lot_values(self, rastro):
        """What to write on the move line for a lot of the NF-e.

        The receipt type decides: an existing lot is used by its id; a type
        that creates lots on validation gets the lot name (no stock.lot yet);
        only a type that does not create lots on validation needs the lot to
        exist now.
        """
        self.ensure_one()
        Lot = self.env["stock.lot"]
        expiration = (
            datetime.combine(rastro.nfe40_dVal, time.min)
            if rastro.nfe40_dVal
            else False
        )
        lot = Lot.search(
            [
                ("name", "=", rastro.nfe40_nLote),
                ("product_id", "=", self.product_id.id),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
        )
        if lot:
            return {"lot_id": lot.id}
        if self.picking_type_id.use_create_lots:
            vals = {"lot_name": rastro.nfe40_nLote}
            if expiration:
                vals["expiration_date"] = expiration
            return vals
        vals = {
            "name": rastro.nfe40_nLote,
            "product_id": self.product_id.id,
            "company_id": self.company_id.id,
        }
        if expiration:
            vals["expiration_date"] = expiration
        if rastro.nfe40_dFab and "production_date" in Lot._fields:
            vals["production_date"] = datetime.combine(rastro.nfe40_dFab, time.min)
        return {"lot_id": Lot.create(vals).id}

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
            line.lot_id
            or line.lot_name
            or line.qty_done
            or line.package_id
            or line.result_package_id
            for line in self.move_line_ids
        ):
            return _(
                "The receipt of %s already has lots or quantities.",
                self.product_id.display_name,
            )
        document_lines = self._nfe_rastro_lines()
        if not document_lines:
            return _("The NF-e has no lot group for %s.", self.product_id.display_name)
        proposals = []
        for document_line in document_lines:
            for rastro in document_line.nfe40_rastro:
                if not rastro.nfe40_nLote:
                    continue
                proposals.append(
                    (
                        document_line.uom_id._compute_quantity(
                            rastro.nfe40_qLote, self.product_uom
                        ),
                        document_line.uom_id._compute_quantity(
                            rastro.nfe40_qLote, self.product_id.uom_id
                        ),
                        self._nfe_lot_values(rastro),
                    )
                )
        if not proposals:
            return _("The NF-e has no lot group for %s.", self.product_id.display_name)
        # the empty lines already there are reused, so that the move keeps its
        # reservation and does not leave the Ready state
        empty_lines = self.move_line_ids
        for index, (quantity, product_quantity, values) in enumerate(proposals):
            line_values = dict(values, qty_done=quantity, reserved_uom_qty=quantity)
            if index < len(empty_lines):
                empty_lines[index].write(line_values)
            else:
                vals = self._prepare_move_line_vals(quantity=product_quantity)
                vals.update(line_values)
                self.env["stock.move.line"].create(vals)
        empty_lines[len(proposals) :].unlink()
        # a move from a supplier is always reservable: the remainder of the
        # quantity, if any, gets its own line and the move stays assigned
        self._action_assign()
        return ""
