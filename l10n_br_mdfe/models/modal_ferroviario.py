# Copyright 2023 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from nfelib.mdfe.bindings.v3_0.mdfe_modal_ferroviario_v3_00 import Ferrov

from odoo import _, api, fields
from odoo.exceptions import UserError

from odoo.addons.spec_driven_model.models import spec_models


class MDFeModalFerroviario(spec_models.SpecModel):
    _name = "l10n_br_mdfe.modal.ferroviario"
    _inherit = "mdfe.30.ferrov"

    mdfe30_trem = fields.Many2one(
        comodel_name="l10n_br_mdfe.modal.ferroviario.trem", required=True
    )

    mdfe30_vag = fields.One2many(comodel_name="l10n_br_mdfe.modal.ferroviario.vagao")


class MDFeModalFerroviarioTrem(spec_models.SpecModel):
    _name = "l10n_br_mdfe.modal.ferroviario.trem"
    _inherit = "mdfe.30.trem"

    mdfe30_xPref = fields.Char(required=True)

    mdfe30_xOri = fields.Char(required=True)

    mdfe30_xDest = fields.Char(required=True)

    mdfe30_qVag = fields.Char(required=True)


class MDFeModalFerroviarioVagao(spec_models.SpecModel):
    _name = "l10n_br_mdfe.modal.ferroviario.vagao"
    _inherit = "mdfe.30.vag"

    document_id = fields.Many2one(comodel_name="l10n_br_fiscal.document")

    mdfe30_pesoBC = fields.Float(required=True)

    mdfe30_pesoR = fields.Float(required=True)

    mdfe30_serie = fields.Char(required=True)

    mdfe30_nVag = fields.Char(required=True)

    mdfe30_TU = fields.Char(required=True)

    @api.constrains("mdfe30_serie")
    def check_serie(self):
        for _record in self.filtered(lambda v: len(v.mdfe30_serie) != 3):
            raise UserError(_("Wagon serie must have exactly 3 digits."))

    @api.constrains("mdfe30_tpVag")
    def check_tp_vag(self):
        for _record in self.filtered(lambda v: len(v.mdfe30_tpVag) != 3):
            raise UserError(_("Wagon type must have exactly 3 digits."))

    @api.model
    def export_fields(self):
        if len(self) > 1:
            return self.export_fields_multi()

        optional_data = {}
        if self.mdfe30_tpVag:
            optional_data["tpVag"] = self.mdfe30_tpVag

        if self.mdfe30_tpVag:
            optional_data["nSeq"] = self.mdfe30_nSeq

        return Ferrov.Vag(
            pesoBC="{:.3f}".format(self.mdfe30_pesoBC),
            pesoR="{:.3f}".format(self.mdfe30_pesoR),
            TU="{:.3f}".format(float(self.mdfe30_TU)),
            serie=self.mdfe30_serie,
            nVag=self.mdfe30_nVag,
            **optional_data
        )

    @api.model
    def export_fields_multi(self):
        return [record.export_fields() for record in self]