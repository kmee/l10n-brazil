# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import Command
from odoo.tests import TransactionCase


class TestDeliveryNFeAccess(TransactionCase):
    def test_invoicing_user_can_write_volumes(self):
        """The invoicing wizard writes volumes as the user billing the picking."""
        user = self.env["res.users"].create(
            {
                "name": "Invoicing user",
                "login": "invoicing_user_vol",
                "groups_id": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("l10n_br_nfe.group_user").id,
                            self.env.ref("account.group_account_invoice").id,
                        ]
                    )
                ],
            }
        )
        for model in ("nfe.40.vol", "nfe.40.lacres"):
            self.env[model].with_user(user).check_access("create")
