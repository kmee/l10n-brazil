# Copyright (C) 2026-Today - KMEE (<https://kmee.com.br>).
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """The overrides of l10n_latam_invoice_document methods moved to
    l10n_br_account_latam_invoice_document. A database that already has the
    Latin American documents installed gets that module now, in the same
    update, so the Brazilian invoices keep the same behaviour."""
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    modules = env["ir.module.module"]
    latam = modules.search(
        [("name", "=", "l10n_latam_invoice_document"), ("state", "=", "installed")]
    )
    bridge = modules.search(
        [
            ("name", "=", "l10n_br_account_latam_invoice_document"),
            ("state", "=", "uninstalled"),
        ]
    )
    if latam and bridge:
        bridge.button_install()
