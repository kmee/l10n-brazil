# Copyright 2026 KMEE INFORMATICA LTDA - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from .stock_landed_cost import BY_CUSTOMS_VALUE


class L10nBrDuimpDeclaracao(models.Model):
    _inherit = "l10n_br_duimp.declaracao"

    picking_ids = fields.Many2many(
        comodel_name="stock.picking",
        string="Receipts",
        compute="_compute_picking_ids",
        help="Receipts whose moves were linked to the items of this DUIMP.",
    )

    picking_count = fields.Integer(compute="_compute_picking_ids")

    expense_document_ids = fields.Many2many(
        comodel_name="l10n_br_fiscal.document",
        relation="l10n_br_duimp_declaracao_expense_document_rel",
        column1="declaracao_id",
        column2="document_id",
        string="Customs Expenses",
        domain="[('company_id', '=', company_id),"
        " ('fiscal_operation_type', '=', 'in'),"
        " ('duimp_declaracao_id', '=', False)]",
        copy=False,
        help="Incoming fiscal documents of the costs of this import (customs"
        " broker, storage, freight) that are allocated to its receipts.",
    )

    landed_cost_ids = fields.Many2many(
        comodel_name="stock.landed.cost",
        compute="_compute_landed_cost_ids",
        string="Landed Costs",
    )

    landed_cost_count = fields.Integer(compute="_compute_landed_cost_ids")

    @api.depends("item_ids.move_ids.picking_id")
    def _compute_picking_ids(self):
        for record in self:
            record.picking_ids = record.item_ids.move_ids.picking_id
            record.picking_count = len(record.picking_ids)

    @api.depends("expense_document_ids.landed_cost_ids")
    def _compute_landed_cost_ids(self):
        for record in self:
            record.landed_cost_ids = record.expense_document_ids.landed_cost_ids
            record.landed_cost_count = len(record.landed_cost_ids)

    def action_link_receipts(self):
        self.ensure_one()
        wizard = self.env["l10n_br_duimp.receipt.link.wizard"].create(
            {"declaracao_id": self.id}
        )
        wizard._suggest_moves()
        return {
            "type": "ir.actions.act_window",
            "res_model": wizard._name,
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    def _check_landed_cost_receipts(self):
        self.ensure_one()
        pending = self.item_ids.filtered("receipt_pending")
        if pending:
            raise UserError(
                _(
                    "Link the receipts of every DUIMP item before allocating its"
                    " expenses. Pending items: %(items)s",
                    items=", ".join(pending.mapped("numero_item")),
                )
            )
        not_done = self.picking_ids.filtered(lambda picking: picking.state != "done")
        if not_done:
            raise UserError(
                _(
                    "Validate the receipts before allocating the expenses: %(names)s",
                    names=", ".join(not_done.mapped("name")),
                )
            )

    def action_create_landed_costs(self):
        """One landed cost per customs expense not allocated yet, on the
        receipts linked to this DUIMP."""
        self.ensure_one()
        self._check_landed_cost_receipts()
        documents = self.expense_document_ids.filtered(
            lambda doc: not doc.landed_cost_ids.filtered(
                lambda cost: cost.state != "cancel"
            )
        )
        if not documents:
            raise UserError(
                _("Every customs expense of this DUIMP already has a landed cost.")
            )
        for document in documents:
            vals = {"landed_cost_picking_ids": [Command.set(self.picking_ids.ids)]}
            if not document.landed_cost_split_method:
                vals["landed_cost_split_method"] = BY_CUSTOMS_VALUE
            document.write(vals)
            document.action_create_landed_cost()
        return self.action_view_landed_costs()

    def action_view_receipts(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock.action_picking_tree_all"
        )
        action["domain"] = [("id", "in", self.picking_ids.ids)]
        action["context"] = {"create": False}
        return action

    def action_view_landed_costs(self):
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "stock_landed_costs.action_stock_landed_cost"
        )
        action["domain"] = [("id", "in", self.landed_cost_ids.ids)]
        action["context"] = {"create": False}
        return action
