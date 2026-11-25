# Copyright 2026 KMEE INFORMATICA LTDA - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class StockLandedCost(models.Model):
    _inherit = "stock.landed.cost"

    fiscal_document_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document",
        string="Source Fiscal Document",
        readonly=True,
        copy=False,
        index="btree_not_null",
        help="Fiscal document (a freight CT-e, for instance) this landed cost"
        " was created from.",
    )
