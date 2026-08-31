# Copyright 2026 KMEE (Ygor Carvalho <ygor.carvalho@kmee.com.br>)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from lxml import etree

from odoo.tests.common import tagged

from .common import AccountMoveBRCommon


@tagged("post_install", "-at_install")
class TestMoveTaxTotalsView(AccountMoveBRCommon):
    chart_template = "generic_coa"

    def _tax_totals_nodes(self):
        arch = etree.fromstring(
            self.env["account.move"].get_view(view_type="form")["arch"]
        )
        return arch.xpath(
            "//field[@name='tax_totals'][@widget='account-tax-totals-field']"
        )

    def test_tax_totals_widget_is_hidden_in_the_brazilian_form(self):
        """The native totals widget must not be rendered next to the fiscal one.

        It recomputes the document total with its own rules and adds the price
        included taxes (ICMS, PIS, COFINS, IBS, CBS) on top of a subtotal that
        already carries them, so both blocks show a different total on the same
        screen.
        """
        nodes = self._tax_totals_nodes()
        self.assertTrue(nodes, "the tax_totals field is expected in the invoice form")
        for node in nodes:
            self.assertEqual(node.get("invisible"), "1")
            self.assertIsNone(
                node.get("attrs"),
                "attrs was dropped in Odoo 17.0 and no longer hides anything",
            )
