# Copyright (C) 2013  Renato Lima - Akretion <renato.lima@akretion.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, fields, models

from ..constants.fiscal import (
    NCM_FOR_SERVICE_REF,
    PRODUCT_FISCAL_TYPE,
    PRODUCT_FISCAL_TYPE_SERVICE
)

from ..constants.icms import ICMS_ORIGIN, ICMS_ORIGIN_DEFAULT


class ProductTemplate(models.Model):
    _inherit = "product.template"

    def _get_default_ncm_id(self):
        fiscal_type = self.env.context.get("default_fiscal_type")
        if fiscal_type == PRODUCT_FISCAL_TYPE_SERVICE:
            return self.env.ref(NCM_FOR_SERVICE_REF)

    fiscal_type = fields.Selection(
        selection=PRODUCT_FISCAL_TYPE,
        string="Fiscal Type")

    icms_origin = fields.Selection(
        selection=ICMS_ORIGIN,
        string="ICMS Origin",
        default=ICMS_ORIGIN_DEFAULT)

    ncm_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.ncm",
        index=True,
        default=_get_default_ncm_id,
        string="NCM")

    nbm_id = fields.Many2one(
        comodel_name='l10n_br_fiscal.nbm',
        index=True,
        string="NBM")

    fiscal_genre_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.product.genre",
        string="Fiscal Genre")

    service_type_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.service.type",
        string="Service Type LC 166",
        domain="[('internal_type', '=', 'normal')]")

    fiscal_genre_code = fields.Char(
        related="fiscal_genre_id.code",
        store=True,
        string="Fiscal Genre Code")

    ipi_guideline_class_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.tax.ipi.guideline.class",
        string="IPI Guideline Class")

    ipi_control_seal_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.tax.ipi.control.seal",
        string="IPI Control Seal")

    nbs_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.nbs",
        index=True,
        string="NBS")

    cest_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.cest",
        index=True,
        string="CEST",
        domain="[('ncm_ids', '=', ncm_id)]")

    uoe_id = fields.Many2one(
        comodel_name="uom.uom",
        related="ncm_id.uoe_id",
        store=True,
        string="Export UoM")

    uoe_factor = fields.Float(
        string="Export UoM Factor",
        default=1.00)

    uot_id = fields.Many2one(
        comodel_name="uom.uom",
        string="Tax UoM")

    uot_factor = fields.Float(
        string="Tax UoM Factor",
        default=0.00)

    # TODO add percent of estimate taxes

    @api.onchange("fiscal_type")
    def _onchange_fiscal_type(self):
        for r in self:
            if r.fiscal_type == PRODUCT_FISCAL_TYPE_SERVICE:
                r.ncm_id = self.env.ref(NCM_FOR_SERVICE_REF)

    @api.onchange("ncm_id", "fiscal_genre_id")
    def _onchange_ncm_id(self):
        for r in self:
            if r.ncm_id:
                r.fiscal_genre_id = self.env["l10n_br_fiscal.product.genre"].search(
                    [("code", "=", r.ncm_id.code[0:2])]
                )

            if r.fiscal_genre_id.code == PRODUCT_FISCAL_TYPE_SERVICE:
                r.ncm_id = self.env.ref(NCM_FOR_SERVICE_REF)
