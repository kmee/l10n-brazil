# Copyright (C) 2024 Diego Paradeda - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models


class StockInvoiceOnshipping(models.TransientModel):
    _inherit = "stock.invoice.onshipping"

    vol_ids = fields.One2many(
        string="Dados dos volumes",
        comodel_name="stock.invoice.onshipping.vol",
        inverse_name="invoice_wizard_id",
    )

    def _build_invoice_values_from_pickings(self, pickings):
        invoice, values = super()._build_invoice_values_from_pickings(pickings)

        # Volumes
        values["nfe40_vol"] = [
            (
                0,
                0,
                self._convert_volumes_to_write(vol_id),
            )
            for vol_id in self.vol_ids
        ]

        return invoice, values

    def _convert_volumes_to_write(self, data):
        """Prepare wizard lines for writing to fiscal document."""
        return {
            "nfe40_qVol": data.nfe40_qVol,
            "nfe40_esp": data.nfe40_esp,
            "nfe40_marca": data.nfe40_marca,
            "nfe40_pesoL": data.nfe40_pesoL,
            "nfe40_pesoB": data.nfe40_pesoB,
        }

    def _get_single_volume_data(self):
        """Case single volume"""
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            active_ids = active_ids[0]
        pick_obj = self.env["stock.picking"]
        picking_id = pick_obj.browse(active_ids)

        vols_data = [
            {
                "nfe40_qVol": 0,
                "nfe40_esp": "",
                "nfe40_marca": 0,
                "nfe40_pesoL": 0,
                "nfe40_pesoB": 0,
            }
        ]

        for line in picking_id.move_line_ids:
            if line.product_id.volume_type == "product_qty":
                vols_data[0]["nfe40_qVol"] += line.qty_done
                vols_data[0]["nfe40_pesoL"] += line.product_id.product_nfe40_pesoL
                vols_data[0]["nfe40_pesoB"] += line.product_id.product_nfe40_pesoB

        return vols_data

    @api.model
    def default_get(self, fields_list):
        """
        Inherit to add default vol_ids
        :param fields_list: list of str
        :return: dict
        """
        result = super().default_get(fields_list)

        vols_data = self._get_single_volume_data()
        vol_ids = [(0, 0, vol) for vol in vols_data]
        result["vol_ids"] = vol_ids
        return result


class StockInvoiceOnshippingVol(models.TransientModel):
    _name = "stock.invoice.onshipping.vol"
    _inherit = "nfe.40.vol"

    invoice_wizard_id = fields.Many2one(
        string="stock.invoice.onshipping",
        comodel_name="stock.invoice.onshipping",
    )
