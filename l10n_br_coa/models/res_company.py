# Copyright (C) 2026 - TODAY KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class ResCompany(models.Model):
    _inherit = "res.company"

    def _compute_uninstalled_l10n_module_ids(self):
        """Do not auto install the core ``l10n_br`` module.

        Once ``account`` is installed, Odoo installs the localization module of
        the company country when a company is created or gets a new country
        (``install_l10n_modules``). For Brazil the chart of accounts and taxes
        come from this module, and the core ``l10n_br`` (and the Enterprise EDI
        modules built on it) conflicts with them. As ``l10n_br_base`` sets
        Brazil as the default country of a new company, every new company or
        branch would install it. It can still be installed on purpose.
        """
        res = super()._compute_uninstalled_l10n_module_ids()
        for company in self:
            company.uninstalled_l10n_module_ids = (
                company.uninstalled_l10n_module_ids.filtered(
                    lambda module: module.name != "l10n_br"
                )
            )
        return res
