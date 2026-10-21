# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Add the deductible IBS/CBS taxes and the IS taxes to existing companies.

The chart template only reaches a company when the chart is loaded, so the
taxes this version added to `account.tax-br_oca.csv` never arrive in a
database where the chart was loaded before. Without the deductible IBS and
CBS taxes an operation that uses deductible taxes adds the IBS/CBS amount to
the receivable again, and the invoice total no longer matches the title.

For each company that has the Brazilian tax groups the script creates only
what is missing, by xmlid, and never touches a tax that already exists:

* a tax with the same name that somebody created by hand (the workaround
  that was in use) is kept as it is and only gets the xmlid, so the
  deductible tax is not applied twice;
* the repartition accounts of the other taxes are not rewritten, only the
  ones of the taxes created here and of the plain IBS and CBS taxes that were
  shipped with no account at all (`only_tax_templates`).

Accounts that the new taxes need and the company does not have are created
by the same helper the chart load uses.
"""

import logging

from openupgradelib import openupgrade

_logger = logging.getLogger(__name__)

NEW_TAX_GROUPS = ["tax_group_is"]
NEW_TAXES = [
    "tax_template_out_ibs_deductible",
    "tax_template_in_ibs_deductible",
    "tax_template_out_cbs_deductible",
    "tax_template_in_cbs_deductible",
    "tax_template_out_is",
    "tax_template_in_is",
    "tax_template_out_is_deductible",
    "tax_template_in_is_deductible",
]
# Taxes that 18.0 shipped without any account on the repartition lines.
TAXES_WITHOUT_ACCOUNT = [
    "tax_template_out_ibs",
    "tax_template_in_ibs",
    "tax_template_out_cbs",
    "tax_template_in_cbs",
]
BR_CHARTS = ("br_oca", "br_oca_generic", "br_oca_simple")


def _company_xmlid(env, company, key):
    """Full xmlid of the company record for a chart key, or None.

    The chart load names it `account.{company}_{key}`, while
    `load_fiscal_taxes` names it `l10n_br_coa.{company}_{key}`.
    """
    for module in ("account", "l10n_br_coa"):
        xmlid = f"{module}.{company.id}_{key}"
        if env.ref(xmlid, raise_if_not_found=False):
            return xmlid
    return None


def _has_br_tax_groups(env, company):
    return bool(_company_xmlid(env, company, "tax_group_ibs"))


def _accounts_flavor(company):
    """Same rule the chart load uses to pick the account codes."""
    if company.chart_template in BR_CHARTS:
        flavor = "itg"
        if company.chart_template == "br_oca_generic" or (
            getattr(company, "tax_framework", False) == "3"
        ):
            flavor = "cfc"
        return flavor, ".GEN"
    # Brazilian taxes added to another chart by `load_fiscal_taxes`.
    return "cfc", ".BR"


def _link_existing_tax(env, company, key, tax):
    env["ir.model.data"].sudo().create(
        {
            "name": f"{company.id}_{key}",
            "module": "account",
            "model": "account.tax",
            "res_id": tax.id,
            "noupdate": True,
        }
    )


def _migrate_company(env, company):
    chart = env["account.chart.template"].with_company(company)
    group_data = chart._get_br_oca_tax_group_data()
    tax_data = chart._get_br_oca_tax_data()

    data = {}
    new_groups = {
        key: group_data[key]
        for key in NEW_TAX_GROUPS
        if key in group_data and not _company_xmlid(env, company, key)
    }
    if new_groups:
        data["account.tax.group"] = new_groups

    new_taxes = {}
    kept_by_hand = 0
    for key in NEW_TAXES:
        if key not in tax_data or _company_xmlid(env, company, key):
            continue
        vals = dict(tax_data[key])
        # A group that already exists may carry either module in its xmlid.
        vals["tax_group_id"] = (
            _company_xmlid(env, company, vals["tax_group_id"]) or vals["tax_group_id"]
        )
        by_hand = env["account.tax"].search(
            [("name", "=", vals["name"]), ("company_id", "=", company.id)], limit=1
        )
        if by_hand:
            _link_existing_tax(env, company, key, by_hand)
            kept_by_hand += 1
            continue
        new_taxes[key] = vals
    if new_taxes:
        data["account.tax"] = new_taxes

    if data:
        chart._load_data(data)
        env.flush_all()
    to_populate = list(new_taxes)
    for key in TAXES_WITHOUT_ACCOUNT:
        xmlid = _company_xmlid(env, company, key)
        tax = env.ref(xmlid) if xmlid else env["account.tax"]
        lines = (
            tax.invoice_repartition_line_ids | tax.refund_repartition_line_ids
        ).filtered(lambda line: line.repartition_type == "tax")
        if lines and not lines.account_id:
            to_populate.append(key)
    if to_populate:
        flavor, suffix = _accounts_flavor(company)
        chart._populate_default_br_tax_accounts(
            company,
            flavor=flavor,
            review_suffix=suffix,
            only_tax_templates=[f"l10n_br_coa.{key}" for key in to_populate],
        )
    _logger.info(
        "l10n_br_coa: company %s: %s tax group(s) and %s tax(es) created, "
        "%s existing tax(es) kept, accounts set on %s tax(es)",
        company.name,
        len(new_groups),
        len(new_taxes),
        kept_by_hand,
        len(to_populate),
    )


@openupgrade.migrate()
def migrate(env, version):
    for company in env["res.company"].with_context(active_test=False).search([]):
        if not _has_br_tax_groups(env, company):
            continue
        _migrate_company(env, company.with_company(company))
