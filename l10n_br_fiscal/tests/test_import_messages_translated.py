# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase
from odoo.tools.translate import _ as translate


class TestImportMessagesTranslated(TransactionCase):
    def test_the_reasons_of_a_zip_entry_are_in_portuguese(self):
        self.env["res.lang"]._activate_lang("pt_BR")
        self.env = self.env(context=dict(self.env.context, lang="pt_BR"))
        self.assertIn(
            "não é uma NF-e",
            translate("the file is not a NF-e the import understands."),
        )
        self.assertIn(
            "veja o log",
            translate("the file could not be imported (see the server log)."),
        )
