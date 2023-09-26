# Copyright 2023 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields

from odoo.addons.spec_driven_model.models import spec_models

from ..constants.mdfe import (
    MDFE_EMIT_TYPE_DEFAULT,
    MDFE_EMIT_TYPES,
    MDFE_ENVIRONMENT_DEFAULT,
    MDFE_ENVIRONMENTS,
    MDFE_TRANSMISSION_DEFAULT,
    MDFE_TRANSMISSIONS,
    MDFE_TRANSP_TYPE,
    MDFE_TRANSP_TYPE_DEFAULT,
    MDFE_VERSION_DEFAULT,
    MDFE_VERSIONS,
)


class ResCompany(spec_models.SpecModel):

    _name = "res.company"
    _inherit = [
        "res.company",
        "mdfe.30.emit",
    ]
    _binding_module = "nfelib.mdfe.bindings.v3_0.mdfe_tipos_basico_v3_00"
    _field_prefix = "mdfe30_"
    _mdfe_search_keys = ["mdfe30_CNPJ", "mdfe30_xNome", "mdfe_xFant"]

    mdfe_version = fields.Selection(
        selection=MDFE_VERSIONS,
        string="MDFe Version",
        default=MDFE_VERSION_DEFAULT,
    )

    mdfe_environment = fields.Selection(
        selection=MDFE_ENVIRONMENTS,
        string="MDFe Environment",
        default=MDFE_ENVIRONMENT_DEFAULT,
    )

    mdfe_emit_type = fields.Selection(
        selection=MDFE_EMIT_TYPES,
        string="MDFe Emit Type",
        default=MDFE_EMIT_TYPE_DEFAULT,
    )

    mdfe_transp_type = fields.Selection(
        selection=MDFE_TRANSP_TYPE,
        string="MDFe Transp Type",
        default=MDFE_TRANSP_TYPE_DEFAULT,
    )

    mdfe_transmission = fields.Selection(
        selection=MDFE_TRANSMISSIONS,
        string="MDFe Transmission",
        copy=False,
        default=MDFE_TRANSMISSION_DEFAULT,
    )

    mdfe30_enderEmit = fields.Many2one(
        comodel_name="res.partner",
        related="partner_id",
    )

    mdfe30_CNPJ = fields.Char(related="partner_id.mdfe30_CNPJ")

    mdfe30_CPF = fields.Char(related="partner_id.mdfe30_CPF")

    mdfe30_xNome = fields.Char(related="partner_id.legal_name")

    mdfe30_xFant = fields.Char(related="partner_id.name")

    mdfe30_IE = fields.Char(related="partner_id.mdfe30_IE")

    mdfe30_fone = fields.Char(related="partner_id.mdfe30_fone")

    mdfe30_choice6 = fields.Selection(
        [("mdfe30_CNPJ", "CNPJ"), ("mdfe30_CPF", "CPF")],
        string="CNPJ ou CPF?",
        compute="_compute_mdfe_data",
    )

    def _compute_mdfe_data(self):
        for rec in self:
            if rec.partner_id.is_company:
                rec.mdfe30_choice6 = "mdfe30_CNPJ"
            else:
                rec.mdfe30_choice6 = "mdfe30_CPF"