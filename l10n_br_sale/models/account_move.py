# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models


class AccountMove(models.Model):
    _inherit = "account.move"

    @api.model
    def default_get(self, fields_list):
        """A customer invoice opened by hand suggests the sale fiscal operation of
        the company, as the sale order does, together with its document type: the
        operation only applies to an invoice with a fiscal document. The suggestion
        is made only when every line of the operation leads to the same document
        type; the user can still change both while the invoice is a draft."""
        res = super().default_get(fields_list)
        if (
            "fiscal_operation_id" not in fields_list
            or "document_type_id" not in fields_list
            or res.get("fiscal_operation_id")
            or res.get("document_type_id")
        ):
            return res
        move_type = res.get("move_type") or self.env.context.get("default_move_type")
        operation = self.env.company.sale_fiscal_operation_id
        if move_type != "out_invoice" or not operation:
            return res
        # same resolution as get_document_type, without its error: a suggestion
        # must not block opening the invoice
        company = self.env.company
        document_types = {
            line.document_type_id or company.document_type_id
            for line in operation.line_ids
        }
        if len(document_types) == 1:
            document_type = document_types.pop()
            if document_type:
                res["fiscal_operation_id"] = operation.id
                res["document_type_id"] = document_type.id
        return res
