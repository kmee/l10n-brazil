# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openupgradelib import openupgrade

# The data of the operation lines is noupdate: an existing database keeps the
# lines of the purchases of assets and of use and consumption with ICMS ST
# without destination, so the creditability map does not reach them.
OPERATION_LINE_DESTINATIONS = {
    "l10n_br_fiscal.fo_compras_compras_ativost": "fixed_asset",
    "l10n_br_fiscal.fo_compras_compras_uso_consumost": "use_consumption",
}


@openupgrade.migrate()
def migrate(env, version):
    """Set the destination of the two operation lines with ST, only where the
    field is empty: what a user chose is never overwritten."""
    for xmlid, destination in OPERATION_LINE_DESTINATIONS.items():
        line = env.ref(xmlid, raise_if_not_found=False)
        if line and not line.product_destination:
            line.product_destination = destination
