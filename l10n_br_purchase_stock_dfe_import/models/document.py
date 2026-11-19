# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class FiscalDocument(models.Model):
    _inherit = "l10n_br_fiscal.document"

    import_divergent = fields.Boolean(
        string="Divergent",
        compute="_compute_import_divergent",
        search="_search_import_divergent",
        help="Some line differs from its purchase order line or receipt by "
        "more than the tolerances of the company. It only warns: nothing is "
        "blocked.",
    )

    @api.depends("fiscal_line_ids.import_divergent")
    def _compute_import_divergent(self):
        for document in self:
            document.import_divergent = any(
                document.fiscal_line_ids.mapped("import_divergent")
            )

    @api.model
    def _search_import_divergent(self, operator, value):
        if operator not in ("=", "!="):
            raise NotImplementedError("Only = and != are supported.")
        lines = self.env["l10n_br_fiscal.document.line"]
        found = lines.search(lines._search_import_divergent("=", True))
        if (operator == "=") == bool(value):
            return [("id", "in", found.document_id.ids)]
        return [("id", "not in", found.document_id.ids)]

    def action_generate_invoice(self):
        self.ensure_one()
        without_entry = self.fiscal_line_ids.filtered(
            lambda line: line._import_needs_stock_entry()
        )
        if without_entry:
            raise UserError(
                _(
                    "%(count)s line(s) of stockable products have no order and "
                    "no receipt. Use Match with Orders to create the receipt, or "
                    "ask a purchase or stock manager to mark the line as without "
                    "stock entry.",
                    count=len(without_entry),
                )
            )
        return super().action_generate_invoice()
