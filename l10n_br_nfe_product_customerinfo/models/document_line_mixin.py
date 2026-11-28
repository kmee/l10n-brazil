# Copyright 2026 KMEE (https://www.kmee.com.br)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class FiscalDocumentLineMixin(models.AbstractModel):
    _inherit = "l10n_br_fiscal.document.line.mixin"

    partner_product_code = fields.Char(
        string="Partner Product Code (cProd)",
        size=60,
        help="Code the partner uses for the product. When filled, it replaces "
        "the product internal reference in the NF-e cProd tag.",
    )

    partner_product_name = fields.Char(
        string="Partner Product Name (xProd)",
        size=120,
        help="Name the partner uses for the product. When filled, it replaces "
        "the product name in the NF-e xProd tag.",
    )

    def _get_partner_product_vals(self, product, partner):
        """Code and name of the product for the partner, from the customer info."""
        if not product or not partner:
            return {}
        customerinfo = product._select_customerinfo(partner=partner)
        return {
            "partner_product_code": customerinfo.product_code or False,
            "partner_product_name": customerinfo.product_name or False,
        }
