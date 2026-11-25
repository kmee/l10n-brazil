# Copyright 2026 KMEE INFORMATICA LTDA - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    landed_cost_net_cost = fields.Boolean(
        string="Landed Costs at Net Cost",
        default=False,
        help="Whether the landed cost created from an incoming fiscal document"
        " (a freight CT-e, for instance) allocates the net acquisition cost,"
        " that is, the document total minus the taxes this company can"
        " recover (art. 301 RIR/2018, CPC 16), or the gross document total.\n\n"
        "Opt-in: the False default allocates the gross amount, which is how"
        " the receipts themselves are valued in this version.",
    )
