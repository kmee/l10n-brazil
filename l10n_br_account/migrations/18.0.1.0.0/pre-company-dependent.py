# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""A plain column left by an older series blocks the creation of the jsonb
column of a company dependent field: keep it aside under another name."""

from openupgradelib import openupgrade

COLUMNS = {
    "l10n_br_fiscal_operation": [
        "journal_id",
        "fiscal_position_id",
        "deductible_taxes",
    ],
    "l10n_br_fiscal_operation_line": ["fiscal_position_id"],
}


@openupgrade.migrate(use_env=False)
def migrate(cr, version):
    if not openupgrade.table_exists(cr, "ir_property"):
        return
    for table, columns in COLUMNS.items():
        for column in columns:
            cr.execute(
                """SELECT data_type FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s""",
                (table, column),
            )
            row = cr.fetchone()
            if row and row[0] != "jsonb":
                openupgrade.rename_columns(
                    cr, {table: [(column, f"_mig_legacy_{column}"[:63])]}
                )
