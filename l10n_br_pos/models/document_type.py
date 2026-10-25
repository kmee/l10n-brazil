# © 2026 KMEE INFORMATICA LTDA (https://kmee.com.br)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, models


class FiscalDocumentType(models.Model):
    _name = "l10n_br_fiscal.document.type"
    _inherit = ["l10n_br_fiscal.document.type", "pos.load.mixin"]

    @api.model
    def _load_pos_data_domain(self, data):
        config = data["pos.config"]["data"][0]
        ids = [
            config.get("simplified_document_type_id"),
            config.get("detailed_document_type_id"),
        ]
        return [("id", "in", [type_id for type_id in ids if type_id])]

    @api.model
    def _load_pos_data_fields(self, config_id):
        return ["id", "code", "name"]
