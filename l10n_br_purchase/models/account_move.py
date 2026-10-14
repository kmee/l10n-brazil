# Copyright (C) 2020  Magno Costa - Akretion
# Copyright (C) 2020  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, models
from odoo.tools import float_compare


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.onchange("purchase_vendor_bill_id", "purchase_id")
    def _onchange_purchase_auto_complete(self):
        if self.purchase_id:
            if self.purchase_id.fiscal_operation_id:
                self.fiscal_operation_id = self.purchase_id.fiscal_operation_id
                if not self.document_type_id:
                    # Testes não passam por aqui, qual seria esse caso de uso?
                    # Porque se não houver o codigo pode ser removido
                    self.document_type_id = self.company_id.document_type_id
        return super()._onchange_purchase_auto_complete()

    # ------------------------------------------------------------------
    # Link imported fiscal document lines to purchase order lines
    #
    # Only purchase_line_id (and invoice_origin) is written on the imported
    # bill lines: quantity, price_unit and product_uom_id proxy to the imported
    # fiscal line and must keep the values of the document (uCom/qCom/vUnCom).
    # ------------------------------------------------------------------

    @api.model
    def _po_link_candidates(self, partner, company, products):
        """Open purchase order lines of the vendor for the given products,
        oldest purchase order first, with the quantity still to be billed
        (ordered minus already billed, whatever the billing policy)."""
        lines = (
            self.env["purchase.order.line"]
            .sudo()
            .search(
                [
                    ("order_id.state", "=", "purchase"),
                    (
                        "order_id.partner_id.commercial_partner_id",
                        "=",
                        partner.commercial_partner_id.id,
                    ),
                    ("order_id.company_id", "=", company.id),
                    ("display_type", "=", False),
                    ("product_id", "in", products.ids),
                ],
                order="date_order, order_id, sequence, id",
            )
        )
        remaining = {line.id: line.product_qty - line.qty_invoiced for line in lines}
        return lines.filtered(lambda line: remaining[line.id] > 0), remaining

    @api.model
    def _po_link_required_quantity(self, aml, pol):
        """Quantity of the bill line expressed in the PO line UoM, or None when
        the UoM categories differ (the line cannot be billed against it)."""
        uom = aml.product_uom_id or pol.product_uom
        if uom.category_id != pol.product_uom.category_id:
            return None
        return uom._compute_quantity(aml.quantity, pol.product_uom, round=False)

    @api.model
    def _po_link_match(self, aml, candidates, remaining):
        """Pick the purchase order line billed by invoice line ``aml``.

        Candidates must have the same product, a compatible UoM category and a
        remaining quantity covering the whole line (no split). The xPed /
        nItemPed of the fiscal line (matched against the PO line partner_order
        / partner_order_line, the PO name or its partner_ref) has priority and,
        when it points to a purchase order, no other order is considered.
        Otherwise the oldest purchase order with enough quantity wins.
        """
        fiscal_line = aml.fiscal_document_line_id
        product = fiscal_line.product_id
        if not product:
            return candidates.browse()
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )

        def eligible(lines):
            res = lines.browse()
            for line in lines:
                needed = self._po_link_required_quantity(aml, line)
                if needed is None:
                    continue
                if (
                    float_compare(
                        remaining[line.id], needed, precision_digits=precision
                    )
                    >= 0
                ):
                    res |= line
            return res

        same_product = candidates.filtered(lambda line: line.product_id == product)
        xped = (fiscal_line.partner_order or "").strip()
        if xped:
            by_order = same_product.filtered(
                lambda line: (line.partner_order or "").strip() == xped
                or xped in (line.order_id.name, line.order_id.partner_ref)
            )
            if by_order:
                nitemped = (fiscal_line.partner_order_line or "").strip()
                found = eligible(by_order)
                if nitemped:
                    exact = found.filtered(
                        lambda line: (line.partner_order_line or "").strip() == nitemped
                    )
                    found = exact or found
                return found[:1]
        return eligible(same_product)[:1]

    @api.model
    def _po_link_set_origin(self, move):
        names = move.invoice_line_ids.purchase_line_id.order_id.mapped("name")
        if not names:
            return
        origins = [x.strip() for x in (move.invoice_origin or "").split(",") if x]
        missing = [name for name in names if name not in origins]
        if missing:
            move.invoice_origin = ", ".join(origins + missing)

    @api.model
    def _po_link_drop_po_lines(self, move, fiscal_document):
        """Draft bill created from a purchase order, then fiscal document
        imported: the lines derived from the purchase order are replaced by the
        lines of the document (which are then linked to the PO lines like in a
        regular import), so nothing is duplicated and the total is the one of
        the document. A note on the bill lists what was removed."""
        amls = move.invoice_line_ids.filtered(
            lambda line: line.purchase_line_id
            and line.fiscal_document_line_id.document_id != fiscal_document
        )
        if not amls:
            return
        note = [
            self.env._(
                "Lines created from purchase orders replaced by the imported "
                "fiscal document %s:",
                fiscal_document.document_number or fiscal_document.display_name,
            )
        ]
        for line in amls:
            note.append(
                f"{line.purchase_line_id.order_id.name}: "
                f"{line.name or line.product_id.display_name} x {line.quantity}"
            )
        stale_fiscal_lines = amls.fiscal_document_line_id
        move.with_context(check_move_validity=False).write(
            {"invoice_line_ids": [(2, line.id) for line in amls]}
        )
        stale_fiscal_lines.exists().unlink()
        move.message_post(body="<br/>".join(note))

    @api.model
    def _po_link_new_lines(self, move, fiscal_document):
        """Link the invoice lines created from the imported fiscal document to
        open purchase order lines of the same vendor."""
        amls = move.invoice_line_ids.filtered(
            lambda line: not line.purchase_line_id
            and line.fiscal_document_line_id.document_id == fiscal_document
            and line.fiscal_document_line_id.product_id
        )
        if not amls:
            return
        candidates, remaining = self._po_link_candidates(
            fiscal_document.partner_id,
            move.company_id,
            amls.fiscal_document_line_id.product_id,
        )
        if not candidates:
            return
        linked = False
        for aml in amls:
            pol = self._po_link_match(aml, candidates, remaining)
            if not pol:
                continue
            remaining[pol.id] -= self._po_link_required_quantity(aml, pol)
            aml.with_context(check_move_validity=False).purchase_line_id = pol
            linked = True
        if linked:
            self._po_link_set_origin(move)

    @api.model
    def import_fiscal_document(
        self, fiscal_document, move_id=None, move_type="in_invoice"
    ):
        move = self.browse(move_id) if move_id else self.browse()
        if (move.move_type if move_id else move_type) != "in_invoice":
            return super().import_fiscal_document(
                fiscal_document, move_id=move_id, move_type=move_type
            )
        if move_id:
            self._po_link_drop_po_lines(move, fiscal_document)
        result = super().import_fiscal_document(
            fiscal_document, move_id=move_id, move_type=move_type
        )
        self._po_link_new_lines(self.browse(result.id), fiscal_document)
        return result
