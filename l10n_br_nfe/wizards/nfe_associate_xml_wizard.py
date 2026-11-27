# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64

from odoo import _, fields, models
from odoo.exceptions import UserError


class NfeAssociateXmlWizard(models.TransientModel):
    _name = "l10n_br_nfe.associate.xml.wizard"
    _description = "Associate the authorized XML to the NF-e"

    document_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document",
        required=True,
        readonly=True,
    )
    xml_file = fields.Binary(string="Authorized XML (nfeProc)", required=True)

    def action_associate_xml(self):
        self.ensure_one()
        if self.document_id.authorization_file_id:
            raise UserError(_("The document already has an authorized XML."))
        self.document_id._nfe_associate_authorized_xml(base64.b64decode(self.xml_file))
        return {"type": "ir.actions.act_window_close"}
