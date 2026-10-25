# © 2026 KMEE INFORMATICA LTDA (https://kmee.com.br)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo import api, models


class PosSession(models.Model):
    _inherit = "pos.session"

    @api.model
    def _load_pos_data_models(self, config_id):
        # the PoS config relates to these types: the frontend needs them to
        # know the code of the document type of an order
        return super()._load_pos_data_models(config_id) + [
            "l10n_br_fiscal.document.type"
        ]
