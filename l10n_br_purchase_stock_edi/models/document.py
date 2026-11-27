# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class FiscalDocument(models.Model):
    _inherit = "l10n_br_fiscal.document"

    import_divergent = fields.Boolean(
        string="Divergent Document",
        compute="_compute_import_divergent",
        search="_search_import_divergent",
        help="Some line differs from its purchase order line or receipt by "
        "more than the tolerances of the company. It only warns: nothing is "
        "blocked.",
    )

    import_awaiting_receipt = fields.Boolean(
        string="Awaiting Receipt",
        compute="_compute_import_awaiting_receipt",
        search="_search_import_awaiting_receipt",
        help="Some line waits for the receipt of its order line. It only informs: "
        "nothing is blocked and it is not a divergence.",
    )

    import_picking_ids = fields.Many2many(
        comodel_name="stock.picking",
        compute="_compute_import_pickings",
        string="Receipts",
        groups="purchase.group_purchase_user,stock.group_stock_user",
        help="Technical: the receipts that the lines of the document point to, "
        "as resolved or as suggested.",
    )
    import_picking_count = fields.Integer(
        compute="_compute_import_pickings",
        string="Receipts",
        groups="purchase.group_purchase_user,stock.group_stock_user",
    )

    @api.depends("fiscal_line_ids.import_awaiting_receipt")
    def _compute_import_awaiting_receipt(self):
        for document in self:
            document.import_awaiting_receipt = any(
                document.fiscal_line_ids.mapped("import_awaiting_receipt")
            )

    @api.model
    def _search_import_awaiting_receipt(self, operator, value):
        if operator not in ("=", "!="):
            raise NotImplementedError("Only = and != are supported.")
        lines = self.env["l10n_br_fiscal.document.line"]
        found = lines.search(lines._search_import_awaiting_receipt("=", True))
        if (operator == "=") == bool(value):
            return [("id", "in", found.document_id.ids)]
        return [("id", "not in", found.document_id.ids)]

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

    @api.depends("fiscal_line_ids.import_stock_move_id")
    def _compute_import_pickings(self):
        for document in self:
            pickings = document.sudo().fiscal_line_ids.import_stock_move_id.picking_id
            document.import_picking_ids = pickings
            document.import_picking_count = len(pickings)

    def action_view_import_pickings(self):
        """The receipt of the document, or the list when there are several."""
        self.ensure_one()
        pickings = self.sudo().fiscal_line_ids.import_stock_move_id.picking_id
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "stock.action_picking_tree_all"
        )
        if len(pickings) == 1:
            action["views"] = [(False, "form")]
            action["res_id"] = pickings.id
        else:
            action["domain"] = [("id", "in", pickings.ids)]
        return action

    def action_fill_import_receipts(self):
        """Fill the receipts the lines point to with what the document says,
        for the operator to review. Nothing is validated."""
        self.ensure_one()
        moves = self.sudo().fiscal_line_ids.import_stock_move_id
        moves._propose_from_import()
        return self.action_view_import_pickings()
