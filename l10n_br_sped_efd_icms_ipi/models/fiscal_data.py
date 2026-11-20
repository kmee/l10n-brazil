# Copyright 2025 - Akretion - Raphael Valyi <raphael.valyi@akretion.com>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class TaxDefinition(models.Model):
    """SPED EFD ICMS/IPI: Tabela 5.3 adjustment code on fiscal benefits."""

    _inherit = "l10n_br_fiscal.tax.definition"

    sped_cod_aj = fields.Char(
        string="SPED Adjustment Code",
        size=10,
        help="Código de ajuste da apuração do ICMS (Tabela 5.3) usado no "
        "registro C197 do SPED EFD ICMS/IPI para este benefício fiscal. "
        "Quando vazio, o C197 usa o cBenef declarado pelo fornecedor.",
    )

    @api.constrains("sped_cod_aj")
    def _check_sped_cod_aj(self):
        _check_sped_cod_aj(self)


class ICMSRelief(models.Model):
    """SPED EFD ICMS/IPI: Tabela 5.3 adjustment code on ICMS relief."""

    _inherit = "l10n_br_fiscal.icms.relief"

    sped_cod_aj = fields.Char(
        string="SPED Adjustment Code",
        size=10,
        help="Código de ajuste da apuração do ICMS (Tabela 5.3) usado no "
        "registro C197 do SPED EFD ICMS/IPI para este motivo de desoneração. "
        "Quando vazio, o C197 usa o cBenef declarado pelo fornecedor.",
    )

    @api.constrains("sped_cod_aj")
    def _check_sped_cod_aj(self):
        _check_sped_cod_aj(self)


def _check_sped_cod_aj(records):
    context = records.env.context  # noqa: F841
    for record in records:
        if record.sped_cod_aj and len(record.sped_cod_aj) != 10:
            raise ValidationError(
                _(
                    "The SPED adjustment code must have exactly 10 positions "
                    "(table 5.3 of the EFD ICMS/IPI): %s",
                    record.sped_cod_aj,
                )
            )
