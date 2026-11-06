# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Carry the account types of the chart to the accounts already loaded.

The chart shipped some accounts with a type that contradicts the group they
live in: prepaid expenses as payables, accumulated depreciation and
amortization as a depreciation expense, equity as a non current liability,
and P&L accounts (revenue deductions, PECLD, equity method, income taxes) as
equity or as a liability. The reports of the localization select by
classification and did not notice; the balance sheet of the core, the year
end closing and the reconciliation go by the type.

Odoo 18 has no `account.account.template`: the CSV the chart load parses is
the source of truth, and the template to account mapping is the
`ir.model.data` the load writes (`{company_id}_{csv key}`). The script
replays the type of the CSV on the existing accounts, fixes the two names
that had a typo and moves the orphan prepaid account (1.1.6.01.99, a group
the chart does not have) to 1.1.4.01.99. It does not create the accounts
this version adds: the chart is loaded once per company.
"""

import logging

from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)

TEMPLATE = "br_oca_simple"
RENAMED = {
    "coa_simple_1140101": (
        "Aluguéis e Arredamentos Pagos Antecipadamente",
        "Aluguéis e Arrendamentos Pagos Antecipadamente",
    ),
    "coa_simple_3320107": ("Vale Refeiçãoo/Refeitório", "Vale Refeição/Refeitório"),
}
MOVED = {"coa_simple_1160199": ("1.1.6.01.99", "1.1.4.01.99")}
# prepaid expenses are not reconciled with a partner
NOT_RECONCILABLE = ("coa_simple_1140101", "coa_simple_1140102", "coa_simple_1160199")


def _chart_accounts(env, company):
    """The accounts of the company that came from the CSV: {csv key: account}."""
    keys = env["account.chart.template"]._parse_csv(TEMPLATE, "account.account")
    data = env["ir.model.data"].search(
        [
            ("model", "=", "account.account"),
            ("name", "in", [f"{company.id}_{key}" for key in keys]),
        ]
    )
    accounts = {}
    for d in data:
        account = env["account.account"].browse(d.res_id).exists()
        if account:
            accounts[d.name.split("_", 1)[1]] = account.with_company(company)
    return keys, accounts


def migrate_companies(env):
    Account = env["account.account"]
    companies = (
        env["res.company"]
        .with_context(active_test=False)
        .search([("chart_template", "=", TEMPLATE)])
    )
    retyped = renamed = moved = 0
    for company in companies:
        keys, accounts = _chart_accounts(env, company)
        for key, account in accounts.items():
            csv_type = keys[key]["account_type"]
            if account.account_type != csv_type:
                account.write({"account_type": csv_type})
                retyped += 1
            if key in RENAMED and account.name == RENAMED[key][0]:
                account.write({"name": RENAMED[key][1]})
                renamed += 1
            if key in MOVED and account.code == MOVED[key][0]:
                taken = Account.with_company(company).search_count(
                    [
                        *Account._check_company_domain(company),
                        ("code", "=", MOVED[key][1]),
                    ]
                )
                if taken:
                    _logger.warning(
                        "%s: %s kept as %s, the code %s is already used",
                        company.name,
                        account.name,
                        account.code,
                        MOVED[key][1],
                    )
                else:
                    account.write({"code": MOVED[key][1]})
                    moved += 1
            if key in NOT_RECONCILABLE and account.reconcile:
                # the core refuses to switch off the reconciliation of an
                # account with items; a reconciled prepaid expense keeps it
                used = env["account.move.line"].search_count(
                    [("account_id", "=", account.id)], limit=1
                )
                if used:
                    _logger.warning(
                        "%s: %s keeps the reconciliation, it has journal items",
                        company.name,
                        account.code,
                    )
                else:
                    account.write({"reconcile": False})
    _logger.info(
        "l10n_br_coa_simple: %s companies, %s accounts retyped, %s renamed, %s moved",
        len(companies),
        retyped,
        renamed,
        moved,
    )


@openupgrade.migrate()
def migrate(env, version):
    migrate_companies(env)
