# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.exceptions import UserError


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def _get_lines_without_volume(self):
        self.ensure_one()
        return self.move_line_ids.filtered(
            lambda line: line.lot_id and not line.volume_id
        )

    def button_validate(self):
        for picking in self.filtered("picking_type_id.require_lot_volume"):
            lines = picking._get_lines_without_volume()
            if lines:
                raise UserError(
                    self.env._(
                        "The following lots are not in a volume. Put every lot "
                        "in a volume before validating this delivery:\n%s",
                        "\n".join(
                            f"- {line.lot_id.name} ({line.product_id.display_name})"
                            for line in lines
                        ),
                    )
                )
        return super().button_validate()
