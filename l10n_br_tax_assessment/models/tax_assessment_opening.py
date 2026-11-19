# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo import fields, models


class TaxAssessmentOpening(models.Model):
    """Credit balance of a tax (ICMS, IPI) that the company already had when it began
    to be assessed by the system: the first assessment starts from it.

    The balance that comes from before the start of the assessment is informed here
    by a person, who stays on the record. The system books no entry for it (the
    balance of the taxes to recover is already in the opening balance sheet). The
    PIS and the COFINS keep their credit by period of origin and type, in the
    opening balance of the EFD Contribuicoes."""

    _name = "l10n_br_tax.assessment.opening"
    _description = "Saldo credor inicial da apuração"
    _order = "company_id, tax_group_id"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Empresa",
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(related="company_id.currency_id")
    tax_group_id = fields.Many2one(
        comodel_name="account.tax.group", string="Grupo de imposto", required=True
    )
    amount = fields.Monetary(
        string="Saldo credor",
        required=True,
        help="Saldo credor do imposto no fim do mês anterior ao início da apuração "
        "pelo sistema (o campo 10 do E110 da primeira apuração).",
    )
    informed_by = fields.Many2one(
        comodel_name="res.users",
        string="Informado por",
        default=lambda self: self.env.user,
        readonly=True,
    )
    informed_on = fields.Datetime(
        string="Informado em", default=fields.Datetime.now, readonly=True
    )

    _sql_constraints = [
        (
            "company_group_unique",
            "unique(company_id, tax_group_id)",
            "Já existe um saldo credor inicial deste imposto para a empresa.",
        ),
        (
            "amount_positive",
            "check(amount >= 0)",
            "O saldo credor não pode ser negativo.",
        ),
    ]
