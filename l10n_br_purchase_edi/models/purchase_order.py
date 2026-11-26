# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models

from odoo.addons.l10n_br_fiscal.constants.fiscal import DOCUMENT_ISSUER_PARTNER


class PurchaseOrder(models.Model):
    _inherit = "purchase.order"

    def button_approve(self, force=False):
        result = super().button_approve(force=force)
        self._suggest_origin_on_imported_lines()
        return result

    def _suggest_origin_on_imported_lines(self):
        """A confirmed order becomes a candidate for the lines of the imported
        documents of its supplier that were waiting for it (a quotation, or an
        order created from the document itself)."""
        orders = self.filtered(lambda order: order.state in ("purchase", "done"))
        if not orders:
            return
        lines = (
            self.env["l10n_br_fiscal.document.line"]
            .sudo()
            .search(
                [
                    ("document_id.imported_document", "=", True),
                    ("document_id.issuer", "=", DOCUMENT_ISSUER_PARTNER),
                    ("document_id.fiscal_operation_type", "in", ("in", False)),
                    ("document_id.company_id", "in", orders.company_id.ids),
                    (
                        "document_id.partner_id.commercial_partner_id",
                        "in",
                        orders.partner_id.commercial_partner_id.ids,
                    ),
                    ("product_id", "in", orders.order_line.product_id.ids),
                    ("import_purchase_line_id", "=", False),
                ]
            )
        )
        lines.filtered(
            lambda line: line.document_id._import_is_open()
        )._suggest_import_origin()
