# Copyright 2026 KMEE (https://www.kmee.com.br)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class DocumentLine(models.Model):
    _inherit = "l10n_br_fiscal.document.line"

    def _export_fields_nfe_40_prod(self, xsd_fields, class_obj, export_dict):
        result = super()._export_fields_nfe_40_prod(xsd_fields, class_obj, export_dict)
        if self.partner_product_code:
            export_dict["cProd"] = self.partner_product_code.replace("\n", "").strip()
        if self.partner_product_name:
            export_dict["xProd"] = self.partner_product_name.replace("\n", " ").strip()
        return result
