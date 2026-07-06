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
            ("v02", "Legado - Versao 1 (fato gerador ate 31/12/2025)"),
            ("v03", "Reforma Tributaria - Versao 2 (IBS/CBS)"),
        ],
        string="Schema NFS-e Paulistana",
        default="v02",
        help=(
            "Versao do schema usada na emissao/transmissao da NFS-e Paulistana.\n"
            "- Legado (Versao 1): layout ate 31/12/2025 (bindings nfselib v02).\n"
            "- Reforma Tributaria (Versao 2): layout com IBS/CBS "
            "(bindings nfselib v03)."
        ),
    )
