# Copyright 2026 KMEE (https://www.kmee.com.br)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class FiscalOperation(models.Model):
    _inherit = "l10n_br_fiscal.operation"

    add_origin_nfe_to_xml = fields.Boolean(
        string="Add Origin Notes to the NF-e",
        help="Documents of this operation get the number of the origin notes in "
        "the additional information for the customer (infCpl).",
    )

    origin_nfes_text = fields.Char(
        string="Origin Notes Text",
        default="NOTAS FISCAIS DE ORIGEM:",
        translate=True,
        help="Text written before the origin notes numbers.",
    )
