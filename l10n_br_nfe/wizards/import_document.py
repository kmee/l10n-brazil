# Copyright (C) 2021  Gabriel Cardoso de Faria - Kmee
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import base64
from openerp import api, fields, models, _


class NfeImport(models.TransientModel):
    """ Importar XML Nota Fiscal Eletrônica """

    _name = "l10n_br_nfe.import_xml"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.user.company_id,
    )

    nfe_xml = fields.Binary(
        string="NFe XML to Import",
    )

    @api.multi
    def import_nfe_xml(self):
        edoc = self.env["l10n_br_fiscal.document"].import_xml(
            base64.b64decode(self.nfe_xml), dry_run=False
        )

        vals = {
            "name": "NFe-Importada-{}.xml".format(edoc.document_key),
            "datas": base64.b64decode(self.nfe_xml),
            "datas_fname": "NFe-Importada-{}.xml".format(edoc.document_key),
            "description":
                u'XML NFe - Importada por XML',
            "res_model": "l10n_br_fiscal.document",
            "res_id": edoc.id
        }

        self.env["ir.attachment"].create(vals)

        return {
            "name": _("Documento Importado"),
            "view_mode": "form",
            "view_type": "form",
            "view_id": self.env.ref("l10n_br_fiscal.document_form").id,
            "res_id": edoc.id,
            "res_model": "l10n_br_fiscal.document",
            "type": "ir.actions.act_window",
            "target": "new",
            "flags": {"form": {"action_buttons": True,
                               "options": {"mode": "edit"}}},
        }
