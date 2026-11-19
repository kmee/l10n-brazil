# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class DFe(models.Model):
    _inherit = "l10n_br_fiscal_dfe.dfe"

    def create_xml_attachment(self, xml):
        result = super().create_xml_attachment(xml)
        if self.fiscal_type == "nfe" and self.document_type_dfe == "complete":
            self.dfe_document_id._dfe_import_requested_xml()
        return result
