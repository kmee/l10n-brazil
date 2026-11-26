# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Link the ICMS FCP ST account tax group to the fiscal ICMS FCP ST tax group.

The chart already had the ICMS FCP ST taxes, but only the chart load and the
demo hook link an account tax group to a fiscal one, so a company that had the
chart before keeps the group without the link. The account taxes only follow
the fiscal taxes through `fiscal_tax_group_id`, and without it an imported
ICMS FCP ST never reaches the payable.

Only the groups with no link are changed: a group that somebody linked by hand
is kept.
"""

import logging

from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)


def link_fcp_st_groups(env):
    fiscal_group = env.ref(
        "l10n_br_fiscal.tax_group_icmsfcp_st", raise_if_not_found=False
    )
    if not fiscal_group:
        return
    names = [
        f"{company.id}_tax_group_icmsfcp_st"
        for company in env["res.company"].with_context(active_test=False).search([])
    ]
    imd_domain = [
        ("model", "=", "account.tax.group"),
        ("module", "in", ("account", "l10n_br_coa")),
        ("name", "in", names),
    ]
    groups = env["account.tax.group"]
    for imd in env["ir.model.data"].sudo().search(imd_domain):
        groups |= env["account.tax.group"].browse(imd.res_id).exists()
    groups = groups.filtered(lambda group: not group.fiscal_tax_group_id)
    groups.write({"fiscal_tax_group_id": fiscal_group.id})
    _logger.info("l10n_br_account: %s ICMS FCP ST tax group(s) linked", len(groups))


@openupgrade.migrate()
def migrate(env, version):
    link_fcp_st_groups(env)
