# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo import Command
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMoveViewCache(TransactionCase):
    """The account.move form arch must not leak between users through the
    view cache (the editable mode depends on the fiscal detail group)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.company_us = cls.env["res.company"].create(
            {"name": "View cache US", "country_id": cls.env.ref("base.us").id}
        )
        base_groups = [
            cls.env.ref("base.group_user").id,
            cls.env.ref("account.group_account_invoice").id,
            cls.env.ref("analytic.group_analytic_accounting").id,
        ]
        detail_group = cls.env.ref("l10n_br_account.group_line_fiscal_detail")
        cls.user_detail = cls._create_user("detail", base_groups + [detail_group.id])
        cls.user_plain = cls._create_user("plain", base_groups)

    @classmethod
    def _create_user(cls, login, group_ids):
        return cls.env["res.users"].create(
            {
                "name": f"View cache {login}",
                "login": f"view_cache_{login}",
                "company_id": cls.company.id,
                "company_ids": [Command.set((cls.company | cls.company_us).ids)],
                "groups_id": [Command.set(group_ids)],
            }
        )

    def _get_form_arch(self, user, company=None, **context):
        company = company or self.company
        env = self.env(
            user=user, context=dict(allowed_company_ids=company.ids, **context)
        )
        views = env["account.move"].get_views([(False, "form")])
        return etree.fromstring(views["views"]["form"]["arch"])

    def test_line_list_editable_is_per_user(self):
        xpath = "//field[@name='invoice_line_ids']/list"
        # back to back, in both orders, so that a shared cache entry would fail
        for first, second in (
            (self.user_plain, self.user_detail),
            (self.user_detail, self.user_plain),
        ):
            self.env.registry.clear_cache("templates")
            arch_first = self._get_form_arch(first)
            arch_second = self._get_form_arch(second)
            for user, arch in ((first, arch_first), (second, arch_second)):
                node = arch.xpath(xpath)[0]
                if user == self.user_detail:
                    self.assertEqual(node.get("editable"), "")
                else:
                    self.assertNotEqual(node.get("editable"), "")

    def test_line_form_analytic_distribution_has_amount_field(self):
        arch = self._get_form_arch(self.user_plain)
        node = arch.xpath(
            "//field[@name='invoice_line_ids']/form//field[@name='analytic_distribution']"
        )[0]
        options = node.get("options") or ""
        self.assertIn("'amount_field': 'price_subtotal'", options)
        self.assertIn("'product_field': 'product_id'", options)
        self.assertIn("'account_field': 'account_id'", options)

    def test_line_list_editable_follows_company_country(self):
        xpath = "//field[@name='invoice_line_ids']/list"
        for companies in (
            (self.company, self.company_us),
            (self.company_us, self.company),
        ):
            self.env.registry.clear_cache("templates")
            archs = [self._get_form_arch(self.user_detail, c) for c in companies]
            for company, arch in zip(companies, archs, strict=True):
                editable = arch.xpath(xpath)[0].get("editable")
                if company == self.company:
                    self.assertEqual(editable, "")
                else:
                    self.assertNotEqual(editable, "")

    def test_line_list_editable_follows_force_context(self):
        xpath = "//field[@name='invoice_line_ids']/list"
        for forced in (True, False):
            self.env.registry.clear_cache("templates")
            arch_first = self._get_form_arch(
                self.user_plain, force_line_fiscal_detail=forced
            )
            arch_second = self._get_form_arch(
                self.user_plain, force_line_fiscal_detail=not forced
            )
            for flag, arch in ((forced, arch_first), (not forced, arch_second)):
                editable = arch.xpath(xpath)[0].get("editable")
                if flag:
                    self.assertEqual(editable, "")
                else:
                    self.assertNotEqual(editable, "")
