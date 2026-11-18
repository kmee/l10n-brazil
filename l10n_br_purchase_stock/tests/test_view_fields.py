# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_br_fiscal.tests.common_view_fields import ViewFieldsCheck


@tagged("post_install", "-at_install")
class TestPurchaseStockViewFields(ViewFieldsCheck, TransactionCase):
    """The views of the purchase order, of the receipt and of their lines."""

    def test_the_fields_of_the_views_exist_in_the_models(self):
        checked = self.check_view_fields(
            ("purchase.order", "purchase.order.line", "stock.picking", "stock.move")
        )
        self.assertGreater(checked, 0)
