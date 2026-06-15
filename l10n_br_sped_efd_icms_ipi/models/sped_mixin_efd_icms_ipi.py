# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class SpecMixinEFDICMSIPI(models.AbstractModel):
    _name = "l10n_br_sped.mixin.efd_icms_ipi"
    _description = "l10n_br_sped.mixin.efd_icms_ipi"
    _inherit = "l10n_br_sped.mixin"

    declaration_id = fields.Many2one(
        comodel_name="l10n_br_sped.efd_icms_ipi.0000",
        required=True,
        ondelete="cascade",
    )

    state = fields.Selection(related="declaration_id.state")
