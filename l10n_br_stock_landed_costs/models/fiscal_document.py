# Copyright 2026 KMEE INFORMATICA LTDA - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, _, fields, models
from odoo.exceptions import UserError

from odoo.addons.stock_landed_costs.models.stock_landed_cost import SPLIT_METHOD


class FiscalDocument(models.Model):
    _inherit = "l10n_br_fiscal.document"

    landed_cost_picking_ids = fields.Many2many(
        comodel_name="stock.picking",
        relation="l10n_br_fiscal_document_landed_cost_picking_rel",
        column1="document_id",
        column2="picking_id",
        string="Receipts to Allocate",
        domain="[('company_id', '=', company_id), ('state', '=', 'done'),"
        " ('picking_type_code', '=', 'incoming')]",
        copy=False,
        help="Receipts the cost of this document (freight, expenses) is"
        " allocated to.",
    )

    landed_cost_split_method = fields.Selection(
        selection=SPLIT_METHOD,
        string="Split Method",
        help="How the cost is split among the receipts. When empty, the"
        " default split method of each cost product applies.",
    )

    landed_cost_ids = fields.One2many(
        comodel_name="stock.landed.cost",
        inverse_name="fiscal_document_id",
        string="Landed Costs of the Document",
        copy=False,
    )

    landed_cost_count = fields.Integer(
        compute="_compute_landed_cost_count",
    )

    def _compute_landed_cost_count(self):
        for record in self:
            record.landed_cost_count = len(record.landed_cost_ids)

    def _get_landed_cost_journal(self):
        self.ensure_one()
        journal = self.company_id.lc_journal_id
        if not journal:
            journal = self.env["account.journal"].search(
                [("company_id", "=", self.company_id.id), ("type", "=", "general")],
                limit=1,
            )
        return journal

    def _prepare_landed_cost_line_vals(self, line, amount):
        self.ensure_one()
        product = line.product_id.with_company(self.company_id)
        accounts = product.product_tmpl_id.get_product_accounts()
        return {
            "name": line.name or product.display_name,
            "product_id": product.id,
            "price_unit": amount,
            "split_method": self.landed_cost_split_method
            or product.split_method_landed_cost
            or "equal",
            "account_id": accounts["stock_input"].id,
        }

    def _prepare_landed_cost_vals(self, cost_lines, journal):
        self.ensure_one()
        return {
            "picking_ids": [Command.set(self.landed_cost_picking_ids.ids)],
            "cost_lines": cost_lines,
            "fiscal_document_id": self.id,
            "account_journal_id": journal.id,
        }

    def _check_landed_cost_allowed(self):
        self.ensure_one()
        if self.fiscal_operation_type != "in":
            raise UserError(
                _("Landed costs can only be created from incoming documents.")
            )
        if not self.landed_cost_picking_ids:
            raise UserError(_("Select the receipts the cost is allocated to."))
        if self.landed_cost_ids.filtered(lambda cost: cost.state != "cancel"):
            raise UserError(
                _(
                    "This document already has a landed cost. Cancel it before"
                    " creating another one, otherwise the cost is counted twice."
                )
            )

    def action_create_landed_cost(self):
        self.ensure_one()
        self._check_landed_cost_allowed()
        cost_lines = []
        missing_product = self.env["l10n_br_fiscal.document.line"]
        for line in self.fiscal_line_ids:
            amount = line._get_landed_cost_amount()
            if self.company_id.currency_id.is_zero(amount):
                continue
            if not line.product_id:
                missing_product |= line
                continue
            vals = self._prepare_landed_cost_line_vals(line, amount)
            cost_lines.append(Command.create(vals))
        if missing_product:
            raise UserError(
                _(
                    "Set a cost product on these lines before creating the"
                    " landed cost: %(lines)s",
                    lines=", ".join(missing_product.mapped("name")),
                )
            )
        if not cost_lines:
            raise UserError(_("No line of this document has a cost to allocate."))
        journal = self._get_landed_cost_journal()
        if not journal:
            raise UserError(
                _(
                    "Set a landed cost journal on the company, or create a"
                    " miscellaneous journal for it."
                )
            )
        landed_cost = self.env["stock.landed.cost"].create(
            self._prepare_landed_cost_vals(cost_lines, journal)
        )
        landed_cost.compute_landed_cost()
        return {
            "type": "ir.actions.act_window",
            "res_model": "stock.landed.cost",
            "res_id": landed_cost.id,
            "view_mode": "form",
        }

    def action_view_landed_costs(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock_landed_costs.action_stock_landed_cost"
        )
        action["domain"] = [("fiscal_document_id", "=", self.id)]
        action["context"] = {"create": False}
        if len(self.landed_cost_ids) == 1:
            action["view_mode"] = "form"
            action["views"] = [(False, "form")]
            action["res_id"] = self.landed_cost_ids.id
        return action
