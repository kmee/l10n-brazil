# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class NFeAdi(models.AbstractModel):
    _inherit = "nfe.40.adi"

    addition_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.import.declaration.addition",
        string="Import Declaration Addition",
        help="The persisted addition this adi group was built from, when "
        "one exists. See nfe.40.di.declaration_id for why this can be empty.",
    )
