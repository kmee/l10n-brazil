# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class L10nBrFiscalDocument(models.Model):
    _inherit = "l10n_br_fiscal.document"

    sale_id = fields.Many2one(
        comodel_name="sale.order",
        string="Sale Order",
        compute="_compute_sale_id",
    )

    client_order_ref = fields.Char(
        string="Customer Reference",
        compute="_compute_client_order_ref",
        store=True,
        readonly=False,
    )

    @api.depends("move_ids.line_ids.sale_line_ids")
    def _compute_sale_id(self):
        for document in self:
            document.sale_id = document.move_ids.line_ids.sale_line_ids.order_id[:1]

    @api.depends(
        "move_ids.move_type",
        "move_ids.ref",
        "move_ids.line_ids.client_order_ref",
    )
    def _compute_client_order_ref(self):
        for document in self:
            moves = document.move_ids.filtered(
                lambda m: m.move_type in ("out_invoice", "out_refund")
            )
            refs = [ref for ref in moves.mapped("ref") if ref]
            for line_ref in moves.line_ids.mapped("client_order_ref"):
                if line_ref and not any(line_ref in ref for ref in refs):
                    refs.append(line_ref)
            # Keep what the user typed in documents without any sale
            if refs or not document.client_order_ref:
                document.client_order_ref = ", ".join(refs) or False
