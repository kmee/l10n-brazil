# Copyright (C) 2024 Diego Paradeda - KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo import fields, models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    number_of_volumes = fields.Integer(
        string="Number of Volumes",
        compute="_compute_number_of_volumes",
        store=False,
        default=0,
        copy=False,
    )

    def _compute_number_of_volumes(self):
        for picking in self:
            if len(picking.invoice_ids) == 1:
                picking.number_of_volumes = sum(
                    [
                        float(v)
                        for v in picking.invoice_ids.mapped(
                            "fiscal_document_id.nfe40_vol.nfe40_qVol"
                        )
                    ]
                )
            else:
                picking.number_of_volumes = 0
