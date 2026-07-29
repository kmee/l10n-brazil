# Copyright 2020 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    provedor_nfse = fields.Selection(
        selection_add=[
            ("paulistana", "Paulistana"),
        ]
    )

    nfse_paulistana_schema = fields.Selection(
        selection=[
            ("v02", "Legado - Versão 1 (fato gerador até 31/12/2025)"),
            ("v03", "Reforma Tributária - Versão 2 (IBS/CBS)"),
        ],
        string="Schema NFS-e Paulistana",
        default="v02",
        help=(
            "Versão do schema usada na emissão/transmissão da NFS-e Paulistana.\n"
            "- Legado (Versão 1): layout até 31/12/2025 (bindings nfselib v02).\n"
            "- Reforma Tributária (Versão 2): layout com IBS/CBS "
            "(bindings nfselib v03)."
        ),
    )
