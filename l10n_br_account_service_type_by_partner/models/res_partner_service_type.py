# Copyright 2024 - TODAY, Kaynnan Lemes <kaynnan.lemes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResPartnerServiceType(models.Model):

    _name = "res.partner.service.type"
    _description = "Partner Service Type"

    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Partner",
    )

    service_type_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.service.type",
        string="Fiscal Service Type",
        domain="[('can_be_selected_on_partner', '=', True)]",
        required=True,
    )

    product_id = fields.Many2one(
        comodel_name="product.product",
        string="Product",
        domain="[('type', '=', 'service'), ('tax_icms_or_issqn', '=', 'issqn')]",
        required=True,
    )

    _sql_constraints = [
        (
            "unique_product_service_type_partner",
            "UNIQUE(product_id, partner_id)",
            "A product can only have one service type per partner.",
        ),
    ]
