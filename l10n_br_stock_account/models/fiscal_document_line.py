# Copyright (C) 2024-Today - KMEE (<https://kmee.com.br>).
# @author Diego Paradeda <diego.paradeda@kmee.com.br>


from odoo import api, fields, models


class FiscalDocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    ##########################
    # NF-e tag: rastro
    ##########################

    nfe40_rastro = fields.One2many(
        comodel_name="nfe.40.rastro",
        inverse_name="nfe40_rastro_prod_id",
        compute="_compute_nfe40_rastro",
        store=True,
    )

    @api.depends("account_line_ids.prod_lot_ids", "document_id.state_edoc")
    def _compute_nfe40_rastro(self):
        for record in self:
            if not record.document_id._need_compute_nfe_tags:
                # TODO: is this necessary?
                continue

            if not record.account_line_ids.prod_lot_ids:
                continue

            nfe40_rastro_data = []

            for lot_id in record.account_line_ids.prod_lot_ids:
                dFab = (
                    lot_id.production_date.date() if lot_id.production_date else False
                )
                dVal = (
                    lot_id.expiration_date.date() if lot_id.expiration_date else False
                )
                lot_dict = {
                    "nfe40_nLote": lot_id.name,
                    "nfe40_qLote": lot_id.product_qty,
                    "nfe40_dFab": dFab,
                    "nfe40_dVal": dVal,
                    "nfe40_cAgreg": "TODO nfe40_cAgreg",
                }

                nfe40_rastro_data.append(lot_dict)

            values = {
                "nfe40_rastro": [
                    (
                        0,
                        0,
                        rastro,
                    )
                    for rastro in nfe40_rastro_data
                ]
            }

            record.write(values)
