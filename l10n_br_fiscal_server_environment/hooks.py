# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.addons.server_environment.uninstall import restore_env_managed_columns


def uninstall_hook(env):
    """Recreate the company columns that server.env.mixin dropped."""
    restore_env_managed_columns(
        env, "res.company", ["nfe_environment", "nfse_environment"]
    )
