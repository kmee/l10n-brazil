# Copyright (C) 2020  Magno Costa - Akretion
# Copyright (C) 2020  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models


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
    # ------------------------------------------------------------------

    @api.model
    def _get_fiscal_lines_to_import(self, fiscal_document, move):
        lines = super()._get_fiscal_lines_to_import(fiscal_document, move)
        skip_ids = self.env.context.get("po_link_reused_fiscal_line_ids")
        if skip_ids:
            lines = lines.filtered(lambda line: line.id not in skip_ids)
        return lines

    @api.model
    def _po_link_candidates_domain(self, partner, company):
        return [
            ("order_id.state", "=", "purchase"),
            (
                "order_id.partner_id.commercial_partner_id",
                "=",
                partner.commercial_partner_id.id,
            ),
            ("order_id.company_id", "=", company.id),
            ("display_type", "=", False),
        ]

    @api.model
    def _po_link_sort(self, pol_lines):
        """Deterministic order: oldest purchase order first."""
        return pol_lines.sorted(
            lambda line: (
                line.order_id.date_order or fields.Datetime.now(),
                line.order_id.id,
                line.sequence,
                line.id,
            )
        )

    @api.model
    def _po_link_match(self, fiscal_line, candidates, remaining):
        """Pick the purchase order line for an imported fiscal line.

        1. xPed / nItemPed (partner_order / partner_order_line) on the fiscal
           line, matched against the PO line fields, the PO name or partner_ref;
        2. else the product, with remaining quantity, oldest PO first.

        :param candidates: purchase.order.line recordset to choose from
        :param remaining: dict pol.id -> quantity still available to bill
        """
        candidates = self._po_link_sort(
            candidates.filtered(lambda line: remaining.get(line.id, 0.0) > 0)
        )
        if not candidates:
            return candidates
        product = fiscal_line.product_id
        xped = (fiscal_line.partner_order or "").strip()
        nitemped = (fiscal_line.partner_order_line or "").strip()
        if xped:
            by_order = candidates.filtered(
                lambda line: (line.partner_order or "").strip() == xped
                or xped in (line.order_id.name, line.order_id.partner_ref)
            )
            if nitemped:
                exact = by_order.filtered(
                    lambda line: (line.partner_order_line or "").strip() == nitemped
                    and (line.partner_order or "").strip() == xped
                )
                if exact:
                    return exact[:1]
            if product:
                by_order = by_order.filtered(lambda line: line.product_id == product)
            if len(by_order) == 1 or (by_order and product):
                return by_order[:1]
        if product:
            return candidates.filtered(lambda line: line.product_id == product)[:1]
        return candidates.browse()

    @api.model
    def _po_link_values(self, from_uom, quantity, price_unit, pol):
        """Values to write on an invoice line to bill ``pol``, keeping the
        purchase order line UoM: quantity/price are converted when the UoMs
        share a category, otherwise they are kept so the line total holds."""
        to_uom = pol.product_uom
        if from_uom and from_uom != to_uom:
            if from_uom.category_id == to_uom.category_id:
                new_qty = from_uom._compute_quantity(quantity, to_uom, round=False)
                if new_qty:
                    price_unit = price_unit * quantity / new_qty
                    quantity = new_qty
        return {
            "purchase_line_id": pol.id,
            "product_uom_id": to_uom.id,
            "quantity": quantity,
            "price_unit": price_unit,
        }

    @api.model
    def _po_link_remaining(self, pols):
        return {line.id: line.qty_to_invoice for line in pols}

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
    def _po_link_reuse_existing_lines(self, move, fiscal_document):
        """Draft bill created from a purchase order: attach the fiscal lines to
        the bill lines already linked to PO lines instead of appending
        duplicates. Returns the fiscal lines that were attached."""
        reused = self.env["l10n_br_fiscal.document.line"]
        amls = move.invoice_line_ids.filtered(
            lambda line: line.purchase_line_id
            and line.fiscal_document_line_id.document_id != fiscal_document
        )
        if not amls:
            return reused
        pols = amls.purchase_line_id
        remaining = {pol.id: 1.0 for pol in pols}  # already on this bill
        write_vals = []
        dummy_lines = self.env["l10n_br_fiscal.document.line"]
        for fiscal_line in fiscal_document.fiscal_line_ids:
            pol = self._po_link_match(fiscal_line, pols, remaining)
            if not pol:
                continue
            aml = amls.filtered(lambda line, pol=pol: line.purchase_line_id == pol)[:1]
            if not aml:
                continue
            amls -= aml
            remaining[pol.id] = 0.0
            vals = self._po_link_values(
                fiscal_line.uot_id,
                fiscal_line.quantity,
                fiscal_line.price_unit,
                pol,
            )
            amt_inc, amt_not_inc = self._get_import_tax_amounts(fiscal_line)
            vals.update(
                {
                    "fiscal_document_line_id": fiscal_line.id,
                    "amount_tax_included": amt_inc,
                    "amount_tax_not_included": amt_not_inc,
                }
            )
            if aml.fiscal_document_line_id != fiscal_line:
                dummy_lines |= aml.fiscal_document_line_id
            write_vals.append((1, aml.id, vals))
            reused |= fiscal_line
        if write_vals:
            move.with_context(check_move_validity=False).write(
                {"invoice_line_ids": write_vals}
            )
            dummy_lines.exists().unlink()
            self._po_link_set_origin(move)
        return reused

    @api.model
    def _po_link_new_lines(self, move, fiscal_document, skip_fiscal_lines):
        """Link the invoice lines just created from the imported fiscal
        document to open purchase order lines of the same vendor."""
        fiscal_lines = fiscal_document.fiscal_line_ids - skip_fiscal_lines
        amls = move.invoice_line_ids.filtered(
            lambda line: not line.purchase_line_id
            and line.fiscal_document_line_id in fiscal_lines
        )
        if not amls:
            return
        candidates = (
            self.env["purchase.order.line"]
            .sudo()
            .search(
                self._po_link_candidates_domain(
                    fiscal_document.partner_id, move.company_id
                )
            )
        )
        if not candidates:
            return
        remaining = self._po_link_remaining(candidates)
        write_vals = []
        for aml in amls:
            fiscal_line = aml.fiscal_document_line_id
            pol = self._po_link_match(fiscal_line, candidates, remaining)
            if not pol:
                continue
            vals = self._po_link_values(
                aml.product_uom_id, aml.quantity, aml.price_unit, pol
            )
            remaining[pol.id] -= vals["quantity"]
            write_vals.append((1, aml.id, vals))
        if write_vals:
            move.with_context(check_move_validity=False).write(
                {"invoice_line_ids": write_vals}
            )
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
        reused = self.env["l10n_br_fiscal.document.line"]
        model = self
        if move_id:
            reused = self._po_link_reuse_existing_lines(move, fiscal_document)
            if reused:
                model = self.with_context(po_link_reused_fiscal_line_ids=reused.ids)
        result = super(AccountMove, model).import_fiscal_document(
            fiscal_document, move_id=move_id, move_type=move_type
        )
        self._po_link_new_lines(self.browse(result.id), fiscal_document, reused)
        return result
