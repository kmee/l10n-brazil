# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import importlib.util
from pathlib import Path

from odoo.tests.common import tagged

from .common import AccountMoveBRCommon


@tagged("post_install", "-at_install")
class TestIcmsFcpStTaxMapping(AccountMoveBRCommon):
    def _migration(self):
        path = (
            Path(__file__).resolve().parents[1]
            / "migrations"
            / "18.0.4.0.8"
            / "post-migration.py"
        )
        spec = importlib.util.spec_from_file_location("fcpst_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _fcp_st_group(self):
        company = self.company_data["company"]
        return (
            self.env["account.tax.group"]
            .sudo()
            .search([("company_id", "=", company.id), ("name", "=", "ICMS FCP ST")])
        )

    def test_the_icms_fcp_st_taxes_are_linked_to_the_fiscal_group(self):
        fiscal_group = self.env.ref("l10n_br_fiscal.tax_group_icmsfcp_st")
        company = self.company_data["company"]
        for use in ("purchase", "sale"):
            tax = self.env["account.tax"].search(
                [
                    ("company_id", "=", company.id),
                    ("type_tax_use", "=", use),
                    ("tax_group_id.name", "=", "ICMS FCP ST"),
                ]
            )
            self.assertEqual(len(tax), 1, use)
            self.assertEqual(tax.tax_group_id.fiscal_tax_group_id, fiscal_group)
            self.assertTrue(tax.fiscal_tax_ids, use)

    def test_the_migration_links_a_company_that_had_the_chart_before(self):
        group = self._fcp_st_group()
        self.assertEqual(len(group), 1)
        group.fiscal_tax_group_id = False

        self._migration().link_fcp_st_groups(self.env(su=True))

        self.assertEqual(
            group.fiscal_tax_group_id,
            self.env.ref("l10n_br_fiscal.tax_group_icmsfcp_st"),
        )

    def test_the_migration_keeps_a_group_linked_by_hand(self):
        group = self._fcp_st_group()
        self.assertEqual(len(group), 1)
        by_hand = self.env.ref("l10n_br_fiscal.tax_group_icmsfcp")
        group.fiscal_tax_group_id = by_hand

        self._migration().link_fcp_st_groups(self.env(su=True))

        self.assertEqual(group.fiscal_tax_group_id, by_hand)
