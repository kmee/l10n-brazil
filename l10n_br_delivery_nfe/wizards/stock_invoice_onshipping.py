# Copyright (C) 2024 Diego Paradeda - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, api, fields, models
from odoo.exceptions import UserError


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
        vol_ids = self.vol_ids.filtered(lambda v: v.picking_id == pickings)
        values["nfe40_vol"] = [
            (
                0,
                0,
                self._convert_volumes_to_write(vol_id),
            )
            for vol_id in vol_ids
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
        picking_ids = self._load_pickings()
        if not picking_ids:
            raise UserError(_("No picking 2binvoiced!"))
        return picking_ids

    def _get_volume_data_package_level(self):
        """Generate a single volume for packages"""
        picking_ids = self._get_picking()

        vols_data = []
        for picking_id in picking_ids:
            if picking_id.package_ids:
                for package_level_id in picking_id.package_level_ids:
                    manual_weight = package_level_id.package_id.shipping_weight
                    vol_data = {
                        "nfe40_qVol": 1,
                        "nfe40_esp": "",
                        "nfe40_marca": "",
                        "nfe40_pesoL": 0,
                        "nfe40_pesoB": (manual_weight if manual_weight else 0),
                        "picking_id": picking_id.id,
                    }

                    for line in package_level_id.move_line_ids:
                        vol_data["nfe40_esp"] = (
                            vol_data["nfe40_esp"] or line.product_id.product_nfe40_esp
                        )
                        product_nfe40_marca = (
                            line.product_id.product_brand_id.name
                            if line.product_id.product_brand_id
                            else ""
                        )
                        vol_data["nfe40_marca"] = (
                            vol_data["nfe40_marca"] or product_nfe40_marca
                        )
                        pesoL = line.qty_done * line.product_id.net_weight
                        pesoB = line.qty_done * line.product_id.weight
                        vol_data["nfe40_pesoL"] += pesoL
                        vol_data["nfe40_pesoB"] += 0 if manual_weight else pesoB
                    vols_data.append(vol_data)

        return vols_data

    def _get_volume_data_wo_package(self):
        """Generate a single volume for lines without package"""
        picking_ids = self._get_picking()

        vols_data = []
        for picking_id in picking_ids:
            # Filter out move lines with in a package
            if not picking_id.move_line_ids_without_package.filtered(
                lambda ml: not ml.package_level_id
            ):
                continue

            new_vol = {
                "nfe40_qVol": 0,
                "nfe40_esp": "",
                "nfe40_marca": "",
                "nfe40_pesoL": 0,
                "nfe40_pesoB": 0,
                "picking_id": picking_id.id,
            }

            for line in picking_id.move_line_ids_without_package.filtered(
                lambda ml: not ml.package_level_id and not ml.result_package_id
            ):
                new_vol["nfe40_qVol"] += line.qty_done
                new_vol["nfe40_esp"] = (
                    new_vol["nfe40_esp"] or line.product_id.product_nfe40_esp
                )
                product_nfe40_marca = (
                    line.product_id.product_brand_id.name
                    if line.product_id.product_brand_id
                    else ""
                )
                new_vol["nfe40_marca"] = new_vol["nfe40_marca"] or product_nfe40_marca
                pesoL = line.qty_done * line.product_id.net_weight
                pesoB = line.qty_done * line.product_id.weight
                new_vol["nfe40_pesoL"] += pesoL
                new_vol["nfe40_pesoB"] += pesoB

            vols_data.append(new_vol)

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
