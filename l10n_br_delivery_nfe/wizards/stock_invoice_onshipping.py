# Copyright (C) 2024 Diego Paradeda - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models


class StockInvoiceOnshipping(models.TransientModel):
    _inherit = "stock.invoice.onshipping"

    vol_ids = fields.One2many(
        string="Volume IDs Data",
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

    def _get_picking(self):
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            active_ids = active_ids[0]
        pick_obj = self.env["stock.picking"]
        return pick_obj.browse(active_ids)

    def _get_volume_data_package_level(self):
        """Generate a single volume for packages"""
        picking_id = self._get_picking()

        vols_data = []
        if picking_id.package_ids:
            for package_level_id in picking_id.package_level_ids:
                manual_weight = package_level_id.package_id.shipping_weight
                vol_data = {
                    "nfe40_qVol": 1,
                    "nfe40_esp": "",
                    "nfe40_marca": "",
                    "nfe40_pesoL": 0,
                    "nfe40_pesoB": (manual_weight if manual_weight else 0),
                }

                for line in package_level_id.move_line_ids:
                    vol_data["nfe40_esp"] = (
                        vol_data["nfe40_esp"] or line.product_id.product_nfe40_esp
                    )
                    vol_data["nfe40_marca"] = (
                        vol_data["nfe40_marca"] or line.product_id.product_nfe40_marca
                    )
                    pesoL = line.qty_done * line.product_id.net_weight
                    pesoB = line.qty_done * line.product_id.weight
                    vol_data["nfe40_pesoL"] += pesoL
                    vol_data["nfe40_pesoB"] += 0 if manual_weight else pesoB
                vols_data.append(vol_data)

        return vols_data

    def _get_volume_data_wo_package(self):
        """Generate a single volume for lines without package"""
        picking_id = self._get_picking()
        # Filter out move lines with in a package
        if not picking_id.move_line_ids_without_package.filtered(
            lambda ml: not ml.package_level_id
        ):
            return []

        vols_data = [
            {
                "nfe40_qVol": 0,
                "nfe40_esp": "",
                "nfe40_marca": "",
                "nfe40_pesoL": 0,
                "nfe40_pesoB": 0,
            }
        ]
        for line in picking_id.move_line_ids_without_package.filtered(
            lambda ml: not ml.package_level_id
        ):
            vols_data[0]["nfe40_qVol"] += line.qty_done
            vols_data[0]["nfe40_esp"] = (
                vols_data[0]["nfe40_esp"] or line.product_id.product_nfe40_esp
            )
            vols_data[0]["nfe40_marca"] = (
                vols_data[0]["nfe40_marca"] or line.product_id.product_nfe40_marca
            )
            pesoL = line.qty_done * line.product_id.net_weight
            pesoB = line.qty_done * line.product_id.weight
            vols_data[0]["nfe40_pesoL"] += pesoL
            vols_data[0]["nfe40_pesoB"] += pesoB

        return vols_data

    def prepare_vols_data(self):
        """Simplify inheritances"""
        vols_data = (
            self._get_volume_data_wo_package() + self._get_volume_data_package_level()
        )
        return vols_data

    @api.model
    def default_get(self, fields_list):
        """
        Inherit to add default vol_ids
        :param fields_list: list of str
        :return: dict
        """
        result = super().default_get(fields_list)
        vol_ids = [(0, 0, vol) for vol in self.prepare_vols_data()]
        result["vol_ids"] = vol_ids
        return result


class StockInvoiceOnshippingVol(models.TransientModel):
    _name = "stock.invoice.onshipping.vol"
    _inherit = "nfe.40.vol"

    invoice_wizard_id = fields.Many2one(
        string="stock.invoice.onshipping",
        comodel_name="stock.invoice.onshipping",
    )
