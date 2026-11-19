# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, models

NO_CREATE_CONTEXT_KEY = "dfe_import_no_create"


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def match_or_create_m2o(self, rec_dict, parent_dict, model=None):
        if not self.env.context.get(NO_CREATE_CONTEXT_KEY):
            return super().match_or_create_m2o(rec_dict, parent_dict, model)
        # dry_run builds the product in memory instead of creating it
        rec_id = super(
            ProductProduct, self.with_context(dry_run=True)
        ).match_or_create_m2o(rec_dict, parent_dict, model)
        if not isinstance(rec_id, models.NewId):
            return rec_id
        # the match of the NF-e only looks at the barcode of the taxable unit
        # (cEANTrib): the one of the commercial unit (cEAN) matches as well
        ean = parent_dict.get("nfe40_cEAN")
        if ean and ean != "SEM GTIN":
            return self.search([("barcode", "=", ean)], limit=1).id or False
        return False
