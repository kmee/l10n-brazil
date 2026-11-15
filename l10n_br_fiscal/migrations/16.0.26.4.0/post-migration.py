# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api

# (operation, return it pointed to before, return it must point to)
RETURN_PAIRS = [
    (
        "fo_remessa_industrializacao",
        "fo_entrada_industrializacao",
        "fo_entrada_retorno_industrializacao",
    ),
    (
        "fo_entrada_industrializacao",
        "fo_remessa_industrializacao",
        "fo_retorno_industrializacao",
    ),
]


def fix_industrializacao_return(env):
    """Point the return of the core contract manufacturing operations to the
    return of the ordering party (1902) instead of the manufacturer entry
    (1901). The records are noupdate, so a plain -u does not change them.

    A return that is not the previous core value was chosen by the user and
    is kept."""
    for operation_xmlid, old_xmlid, new_xmlid in RETURN_PAIRS:
        operation = env.ref(f"l10n_br_fiscal.{operation_xmlid}", False)
        old = env.ref(f"l10n_br_fiscal.{old_xmlid}", False)
        new = env.ref(f"l10n_br_fiscal.{new_xmlid}", False)
        if operation and new and operation.return_fiscal_operation_id == old:
            operation.return_fiscal_operation_id = new


def migrate(cr, version):
    fix_industrializacao_return(api.Environment(cr, SUPERUSER_ID, {}))
