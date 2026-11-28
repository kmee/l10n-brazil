# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Company dependent fields moved from ir.property to a jsonb column."""

from openupgradelib import openupgrade, openupgrade_180

FIELDS = [
    ("l10n_br_fiscal.operation", "journal_id"),
    ("l10n_br_fiscal.operation", "fiscal_position_id"),
    ("l10n_br_fiscal.operation", "deductible_taxes"),
    ("l10n_br_fiscal.operation.line", "fiscal_position_id"),
]


@openupgrade.migrate()
def migrate(env, version):
    for model, field in FIELDS:
        openupgrade_180.convert_company_dependent(env, model, field)
