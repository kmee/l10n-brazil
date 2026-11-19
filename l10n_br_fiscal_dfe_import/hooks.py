# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api

ORIGINAL_MENU_ACTIONS = {
    "l10n_br_nfe.nfe_import_document": "l10n_br_nfe.l10n_br_nfe_import_xml_action",
    "l10n_br_nfe.imported_document_menu": "l10n_br_nfe.imported_document_action",
}


def uninstall_hook(cr, registry):
    """Give the menus taken over by this module back to the original actions."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    for menu_xmlid, action_xmlid in ORIGINAL_MENU_ACTIONS.items():
        action = env.ref(action_xmlid)
        env.ref(menu_xmlid).action = f"{action._name},{action.id}"
