# Copyright (C) 2026 - TODAY KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestCompanyL10nAutoInstall(TransactionCase):
    def test_core_l10n_br_not_auto_installed(self):
        """A Brazilian company must not trigger the core l10n_br install."""
        core_l10n_br = self.env["ir.module.module"].search([("name", "=", "l10n_br")])
        if not core_l10n_br or core_l10n_br.state == "installed":
            self.skipTest("core l10n_br is not available or is already installed")
        brazil = self.env.ref("base.br")
        self.assertIn(brazil, core_l10n_br.country_ids)
        company = self.env["res.company"].create(
            {"name": "Empresa BR", "country_id": brazil.id}
        )
        self.assertNotIn("l10n_br", company.uninstalled_l10n_module_ids.mapped("name"))
