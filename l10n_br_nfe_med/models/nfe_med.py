# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re

from odoo import _, api, models
from odoo.exceptions import ValidationError

# leiauteNFe_v4.00.xsd, med/cProdANVISA
ANVISA_CODE_PATTERN = re.compile(r"[0-9]{11}|[0-9]{13}|ISENTO")


class NFeMed(models.AbstractModel):
    _inherit = "nfe.40.med"

    @api.depends("nfe40_cProdANVISA", "nfe40_vPMC")
    def _compute_display_name(self):
        for record in self:
            record.display_name = (
                f"{record.nfe40_cProdANVISA or ''} - PMC {record.nfe40_vPMC:.2f}"
            )

    @api.constrains("nfe40_cProdANVISA")
    def _check_nfe40_cProdANVISA(self):
        for record in self:
            if not ANVISA_CODE_PATTERN.fullmatch(record.nfe40_cProdANVISA or ""):
                raise ValidationError(
                    _(
                        "The ANVISA code must have 11 or 13 digits, or be ISENTO "
                        "for medicines exempt from registration."
                    )
                )
