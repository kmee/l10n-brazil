# Copyright (C) 2020  Magno Costa - Akretion
# Copyright (C) 2020  Renato Lima - Akretion
# Copyright (C) 2026 - Madooit
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = "account.move"

    show_po_from_nfe_buttons = fields.Boolean(
        compute="_compute_show_po_from_nfe_buttons",
        help="Technical: a vendor bill of an imported document that still has "
        "product lines not linked to a purchase order.",
    )

    has_unconfirmed_import_origin = fields.Boolean(
        compute="_compute_has_unconfirmed_import_origin",
        help="Technical: a draft vendor bill of an imported document that has a "
        "line whose purchase order origin was only suggested or is still "
        "pending, so the destination of the order was not applied.",
    )

    @api.depends(
        "state",
        "move_type",
        "fiscal_document_id.imported_document",
        "fiscal_document_id.fiscal_line_ids.import_origin_state",
    )
    def _compute_has_unconfirmed_import_origin(self):
        for move in self:
            document = move.fiscal_document_id
            move.has_unconfirmed_import_origin = bool(
                move.state == "draft"
                and move.move_type == "in_invoice"
                and document.imported_document
                and {"suggested", "pending"}
                & set(document.fiscal_line_ids.mapped("import_origin_state"))
            )

    @api.depends(
        "move_type",
        "fiscal_document_id.imported_document",
        "invoice_line_ids.product_id",
        "invoice_line_ids.purchase_line_id",
    )
    def _compute_show_po_from_nfe_buttons(self):
        for move in self:
            move.show_po_from_nfe_buttons = bool(
                move.move_type == "in_invoice"
                and move.fiscal_document_id.imported_document
                and move._get_nfe_lines_without_purchase_line()
            )

    def _get_nfe_lines_without_purchase_line(self):
        self.ensure_one()
        return self.invoice_line_ids.filtered(
            lambda line: line.display_type == "product"
            and line.product_id
            and not line.purchase_line_id
        )

    def action_update_po_from_nfe(self):
        self.ensure_one()
        wizard_model = self.env["purchase.update.from.nfe.wizard"]
        vals = wizard_model._get_wizard_vals_from_move(self)
        if not vals.get("line_ids"):
            raise UserError(
                _("No matching purchase order line found for the imported document.")
            )
        wizard = wizard_model.create(vals)
        return {
            "name": _("Update PO from NFe"),
            "type": "ir.actions.act_window",
            "res_model": "purchase.update.from.nfe.wizard",
            "view_mode": "form",
            "res_id": wizard.id,
            "target": "new",
        }

    def action_create_po_from_nfe(self):
        self.ensure_one()
        if self.move_type != "in_invoice":
            raise UserError(
                _("A purchase order can only be created from a vendor bill.")
            )
        if not self.fiscal_document_id:
            raise UserError(_("The vendor bill has no imported fiscal document."))
        bill_lines = self._get_nfe_lines_without_purchase_line()
        if not bill_lines:
            raise UserError(
                _(
                    "All the lines of the vendor bill are already linked to a "
                    "purchase order."
                )
            )
        po = self.env["purchase.order"].create(
            self._prepare_po_from_nfe_vals(bill_lines)
        )
        for bill_line, po_line in zip(bill_lines, po.order_line, strict=True):
            bill_line.purchase_line_id = po_line
        for po_line in po.order_line:
            po_line._onchange_fiscal_tax_ids()
            po_line._compute_tax_fields()
            po_line._compute_amount()
        return {
            "name": _("Purchase Order"),
            "type": "ir.actions.act_window",
            "res_model": "purchase.order",
            "view_mode": "form",
            "res_id": po.id,
        }

    def _prepare_po_from_nfe_vals(self, bill_lines=None):
        self.ensure_one()
        fiscal_doc = self.fiscal_document_id
        order_lines = []
        if bill_lines is None:
            bill_lines = self.invoice_line_ids.filtered("product_id")
        for bill_line in bill_lines:
            line_vals = self._prepare_po_line_from_nfe_vals(bill_line)
            if line_vals:
                order_lines.append((0, 0, line_vals))
        return {
            "partner_id": self.partner_id.id,
            "company_id": self.company_id.id,
            "currency_id": self.currency_id.id,
            "date_order": fiscal_doc.document_date or self.invoice_date,
            "partner_ref": fiscal_doc.document_key
            or (f"{fiscal_doc.document_serie} / {fiscal_doc.document_number}"),
            "fiscal_operation_id": (
                fiscal_doc.fiscal_operation_id or self.fiscal_operation_id
            ).id,
            "order_line": order_lines,
        }

    def _prepare_po_line_from_nfe_vals(self, bill_line):
        self.ensure_one()
        product = bill_line.product_id
        if not product:
            return {}
        product_uom = product.uom_po_id or product.uom_id
        uom = bill_line.uom_id or bill_line.product_uom_id
        quantity = bill_line.quantity
        price_unit = bill_line.price_unit
        if uom and product_uom and uom != product_uom:
            factor = uom._compute_quantity(1.0, product_uom)
            quantity = bill_line.quantity * factor
            price_unit = bill_line.price_unit * factor
        fiscal_vals = bill_line.fiscal_document_line_id._prepare_br_fiscal_dict()
        for key in (
            "name",
            "product_id",
            "quantity",
            "uom_id",
            "fiscal_quantity",
            "taxes_id",
            "price_unit",
        ):
            fiscal_vals.pop(key, None)
        vals = {
            "name": bill_line.name,
            "product_id": product.id,
            "product_qty": quantity,
            "product_uom": product_uom.id,
            "price_unit": price_unit,
        }
        vals.update(fiscal_vals)
        return vals

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
        """Link the imported bill lines to the purchase order lines decided
        on the lines of the imported document (suggested or resolved origin),
        so the order counts the quantity as invoiced.

        A document line without origin still falls back to the xPed and
        nItemPed it carries. A purchase order line is linked to one bill line
        only; anything else stays unlinked.
        """
        self.ensure_one()
        if self.move_type != "in_invoice":
            return
        PurchaseLine = self.env["purchase.order.line"]
        taken = self.invoice_line_ids.purchase_line_id
        for line in self.invoice_line_ids.filtered(
            lambda aml: aml.display_type == "product" and not aml.purchase_line_id
        ):
            fiscal_line = line.fiscal_document_line_id
            purchase_line = fiscal_line.import_purchase_line_id
            if not purchase_line and not fiscal_line.import_origin_state:
                purchase_line = PurchaseLine._find_by_import_reference(
                    self.company_id,
                    self.commercial_partner_id,
                    (fiscal_line.partner_order or "").strip(),
                    fiscal_line.partner_order_line,
                    line.product_id,
                )
            if purchase_line and purchase_line not in taken:
                line.purchase_line_id = purchase_line
                taken |= purchase_line
        if taken and not self.invoice_origin:
            self.invoice_origin = ", ".join(taken.order_id.mapped("name"))
