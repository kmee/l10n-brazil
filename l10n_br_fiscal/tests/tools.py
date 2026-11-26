# Copyright (C) 2026 - TODAY KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from lxml import etree

from odoo import Command
from odoo.tests import new_test_user


def assert_line_edit_mode_follows_group(case, model, lines_field, groups, company):
    """Render the cached form view of model for a user without and with the
    fiscal detail group (the last of groups), in both orders: the lines list
    must be editable inline only without the group."""
    users = [
        new_test_user(
            case.env,
            login=f"{model}.{lines_field}.{detail}",
            groups=",".join(groups if detail else groups[:-1]),
            company_id=company.id,
            company_ids=[Command.set(company.ids)],
        )
        for detail in (False, True)
    ]
    for order in (users, users[::-1]):
        case.env.registry.clear_caches()
        for user in order:
            arch = (
                case.env[model]
                .with_user(user)
                .with_company(company)
                .get_view(view_type="form")["arch"]
            )
            mode = (
                etree.fromstring(arch)
                .xpath(f"//field[@name='{lines_field}']/tree")[0]
                .get("editable")
            )
            if user == users[1]:
                case.assertEqual(mode, "")
            else:
                case.assertTrue(mode)


def assert_fiscal_fields_follow_company(case, model, company):
    """A foreign company must not get the cached form view of a Brazilian one,
    in both orders: only the Brazilian company gets the fiscal fields."""
    foreign = case.env["res.company"].create(
        {"name": f"Foreign company {model}", "country_id": case.env.ref("base.us").id}
    )
    for order in ((company, foreign), (foreign, company)):
        case.env.registry.clear_caches()
        for comp in order:
            arch = case.env[model].with_company(comp).get_view(view_type="form")["arch"]
            if comp == company:
                case.assertIn('name="icms_cst_id"', arch)
            else:
                case.assertNotIn('name="icms_cst_id"', arch)
