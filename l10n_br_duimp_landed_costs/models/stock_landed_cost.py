# Copyright 2026 KMEE INFORMATICA LTDA - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import UserError

BY_CUSTOMS_VALUE = "by_customs_value"
SPLIT_METHOD_CUSTOMS_VALUE = [(BY_CUSTOMS_VALUE, "By Customs Value")]


class StockLandedCost(models.Model):
    _inherit = "stock.landed.cost"

    def compute_landed_cost(self):
        """Split the cost lines that go by customs value.

        The core does not know this method and splits those lines equally;
        their adjustment lines are rewritten here, after the core created
        them, so the other split methods keep the core behavior untouched.
        """
        res = super().compute_landed_cost()
        for cost in self:
            cost_lines = cost.cost_lines.filtered(
                lambda line: line.split_method == BY_CUSTOMS_VALUE
            )
            if cost_lines and cost.valuation_adjustment_lines:
                cost._split_by_customs_value(cost_lines)
        return res

    def _split_by_customs_value(self, cost_lines):
        self.ensure_one()
        adjustments = self.valuation_adjustment_lines
        without_item = adjustments.move_id.filtered(lambda move: not move.duimp_item_id)
        if without_item:
            raise UserError(
                _(
                    "Splitting by customs value needs every receipt line to be"
                    " linked to a DUIMP item. Not linked: %(products)s",
                    products=", ".join(without_item.product_id.mapped("display_name")),
                )
            )
        currency = self.currency_id
        for cost_line in cost_lines:
            line_adjustments = adjustments.filtered(
                lambda adj, cost_line=cost_line: adj.cost_line_id == cost_line
            )
            customs_values = [
                adj.move_id._get_duimp_customs_value() for adj in line_adjustments
            ]
            total = sum(customs_values)
            if currency.is_zero(total):
                raise UserError(
                    _(
                        "The DUIMP items of these receipts have no customs value:"
                        " the cost %(cost)s cannot be split by customs value.",
                        cost=cost_line.name,
                    )
                )
            # The last line takes the rounding difference, so the split always
            # adds up to the cost line.
            remaining = cost_line.price_unit
            for index, (adjustment, customs_value) in enumerate(
                zip(line_adjustments, customs_values, strict=True)
            ):
                if index == len(line_adjustments) - 1:
                    value = remaining
                else:
                    value = currency.round(cost_line.price_unit * customs_value / total)
                remaining -= value
                adjustment.write(
                    {"additional_landed_cost": value, "customs_value": customs_value}
                )


class StockLandedCostLine(models.Model):
    _inherit = "stock.landed.cost.lines"

    split_method = fields.Selection(
        selection_add=SPLIT_METHOD_CUSTOMS_VALUE,
        ondelete={
            BY_CUSTOMS_VALUE: lambda lines: lines.write({"split_method": "equal"})
        },
    )


class AdjustmentLines(models.Model):
    _inherit = "stock.valuation.adjustment.lines"

    customs_value = fields.Monetary(
        help="Customs value of the DUIMP item received by this line, the weight"
        " of the split by customs value.",
    )
