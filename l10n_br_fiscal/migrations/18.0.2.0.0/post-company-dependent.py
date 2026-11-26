# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Company dependent fields moved from ir.property to a jsonb column."""

from openupgradelib import openupgrade, openupgrade_180

FIELDS = [
    ("product.template", "fiscal_type"),
    ("product.template", "icms_origin"),
    ("l10n_br_fiscal.operation.document.type", "document_serie_id"),
]


@openupgrade.migrate()
def migrate(env, version):
    for model, field in FIELDS:
        openupgrade_180.convert_company_dependent(env, model, field)
