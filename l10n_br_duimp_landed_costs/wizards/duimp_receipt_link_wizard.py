# Copyright 2026 KMEE INFORMATICA LTDA - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare


class DuimpReceiptLinkWizard(models.TransientModel):
    _name = "l10n_br_duimp.receipt.link.wizard"
    _description = "Link DUIMP Items to Receipts"

    declaracao_id = fields.Many2one(
        comodel_name="l10n_br_duimp.declaracao",
        required=True,
        ondelete="cascade",
    )

    line_ids = fields.One2many(
        comodel_name="l10n_br_duimp.receipt.link.wizard.line",
        inverse_name="wizard_id",
    )

    def _candidate_moves(self, item):
        return self.env["stock.move"].search(
            [
                ("company_id", "=", item.company_id.id),
                ("product_id", "=", item.product_id.id),
                ("picking_code", "=", "incoming"),
                ("state", "not in", ("draft", "cancel")),
                ("duimp_item_id", "=", False),
            ]
        )

    def _suggest_moves(self):
        """One line per item still pending, with a move suggested only when
        exactly one receipt line has the same product and the quantity still
        missing. Anything else is left for the user to choose."""
        self.ensure_one()
        precision = self.env["decimal.precision"].precision_get(
            "Product Unit of Measure"
        )
        suggested = self.env["stock.move"]
        lines = []
        for item in self.declaracao_id.item_ids.filtered("receipt_pending"):
            missing_qty = item.quantidade - item.received_qty
            candidates = self._candidate_moves(item) - suggested
            matches = candidates.filtered(
                lambda move, item=item, missing_qty=missing_qty: float_compare(
                    move._get_duimp_item_qty(item),
                    missing_qty,
                    precision_digits=precision,
                )
                == 0
            )
            move = matches if len(matches) == 1 else self.env["stock.move"]
            suggested |= move
            lines.append(
                fields.Command.create(
                    {"item_id": item.id, "move_id": move.id, "suggested": bool(move)}
                )
            )
        self.line_ids = lines

    def action_confirm(self):
        self.ensure_one()
        lines = self.line_ids.filtered("move_id")
        if not lines:
            raise UserError(_("Choose the receipt line of at least one item."))
        if len(lines.move_id) != len(lines):
            raise UserError(_("A receipt line can only receive one DUIMP item."))
        already_linked = lines.move_id.filtered("duimp_item_id")
        if already_linked:
            raise UserError(
                _(
                    "These receipt lines are already linked to a DUIMP item:"
                    " %(products)s",
                    products=", ".join(
                        already_linked.product_id.mapped("display_name")
                    ),
                )
            )
        for line in lines:
            line.move_id.duimp_item_id = line.item_id
        return {"type": "ir.actions.act_window_close"}


class DuimpReceiptLinkWizardLine(models.TransientModel):
    _name = "l10n_br_duimp.receipt.link.wizard.line"
    _description = "Link DUIMP Items to Receipts (line)"

    wizard_id = fields.Many2one(
        comodel_name="l10n_br_duimp.receipt.link.wizard",
        required=True,
        ondelete="cascade",
    )
    item_id = fields.Many2one(
        comodel_name="l10n_br_duimp.item",
        required=True,
        readonly=True,
        ondelete="cascade",
    )
    product_id = fields.Many2one(related="item_id.product_id")
    company_id = fields.Many2one(related="item_id.company_id")
    quantity = fields.Float(related="item_id.quantidade")
    received_qty = fields.Float(related="item_id.received_qty")
    move_id = fields.Many2one(
        comodel_name="stock.move",
        string="Receipt Line",
        domain="[('company_id', '=', company_id),"
        " ('product_id', '=', product_id), ('picking_code', '=', 'incoming'),"
        " ('state', 'not in', ('draft', 'cancel')), ('duimp_item_id', '=', False)]",
    )
    suggested = fields.Boolean(
        readonly=True,
        help="The receipt line was suggested by product and quantity; review it"
        " before confirming.",
    )

    @api.onchange("move_id")
    def _onchange_move_id(self):
        self.suggested = False
