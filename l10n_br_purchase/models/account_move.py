# Copyright (C) 2020  Magno Costa - Akretion
# Copyright (C) 2020  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, models


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

    @api.model
    def import_fiscal_document(
        self, fiscal_document, move_id=None, move_type="in_invoice"
    ):
        move_form = super().import_fiscal_document(
            fiscal_document, move_id=move_id, move_type=move_type
        )
        self.browse(move_form.id)._link_purchase_lines_from_fiscal_reference()
        return move_form

    def _link_purchase_lines_from_fiscal_reference(self):
        """Link the imported bill lines to the purchase order lines the
        supplier referred to (xPed and nItemPed of the fiscal document line),
        so the order counts the quantity as invoiced.

        A line is linked only when the reference identifies exactly one open
        purchase order line of the same supplier and product, not already
        taken by another line of this bill. Anything else stays unlinked.
        """
        self.ensure_one()
        if self.move_type != "in_invoice":
            return
        taken = self.invoice_line_ids.purchase_line_id
        for line in self.invoice_line_ids.filtered(
            lambda aml: aml.display_type == "product" and not aml.purchase_line_id
        ):
            fiscal_line = line.fiscal_document_line_id
            order_name = (fiscal_line.partner_order or "").strip()
            if not order_name:
                continue
            purchase_line = self._get_purchase_line_from_reference(
                order_name, fiscal_line.partner_order_line, line.product_id
            )
            if purchase_line and purchase_line not in taken:
                line.purchase_line_id = purchase_line
                taken |= purchase_line

    def _get_purchase_line_from_reference(self, order_name, item, product):
        self.ensure_one()
        orders = self.env["purchase.order"].search(
            [
                ("name", "=", order_name),
                ("company_id", "=", self.company_id.id),
                ("state", "in", ("purchase", "done")),
                (
                    "partner_id.commercial_partner_id",
                    "=",
                    self.commercial_partner_id.id,
                ),
            ]
        )
        if len(orders) != 1:
            return self.env["purchase.order.line"]
        # nItemPed is the 1-based position of the line in the order
        order_lines = orders.order_line.sorted(lambda pol: (pol.sequence, pol.id))
        digits = "".join(char for char in (item or "") if char.isdigit())
        if digits:
            position = int(digits)
            candidates = order_lines[position - 1 : position] if position else []
        else:
            candidates = order_lines
        candidates = order_lines.browse(
            [pol.id for pol in candidates if pol.product_id == product]
        )
        return candidates if len(candidates) == 1 else order_lines.browse()
