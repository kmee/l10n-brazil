# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl-3.0.html).

from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_br_fiscal.tests.common_view_fields import ViewFieldsCheck


@tagged("post_install", "-at_install")
class TestAccountViewFields(ViewFieldsCheck, TransactionCase):
    """The views of the invoice, of its lines and of the fiscal document."""

    def test_the_fields_of_the_views_exist_in_the_models(self):
        checked = self.check_view_fields(
            (
                "l10n_br_fiscal.document",
                "l10n_br_fiscal.document.line",
                "account.move",
                "account.move.line",
            )
        )
        self.assertGreater(checked, 0)
