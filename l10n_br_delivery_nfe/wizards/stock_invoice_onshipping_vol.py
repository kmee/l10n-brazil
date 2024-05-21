# Copyright (C) 2024 Diego Paradeda - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import fields, models


class StockInvoiceOnshippingVol(models.TransientModel):
    _name = "stock.invoice.onshipping.vol"
    _inherit = "nfe.40.vol"

    invoice_wizard_id = fields.Many2one(
        string="stock.invoice.onshipping",
        comodel_name="stock.invoice.onshipping",
    )

    picking_id = fields.Many2one("stock.picking", "Transfer", readonly=True)
