# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from . import common


@tagged("post_install", "-at_install")
class TestImportWizardReview(common.ImportWizardCommon):
    """What the import resolves by itself and what waits for a person."""

    def test_the_order_declared_by_the_supplier_resolves_product_and_origin(self):
        wizard = self._wizard(self._declared_xml())
        line = wizard.imported_products_ids
        self.assertEqual(line.product_source, "order")
        self.assertTrue(line.match_source_trusted)
        wizard._import_edoc()
        fiscal_line = wizard.document_id.fiscal_line_ids
        self.assertEqual(fiscal_line.import_state, "resolved")
        self.assertEqual(fiscal_line.import_purchase_line_id, self.order.order_line)
        self.assertEqual(fiscal_line.import_origin_state, "resolved")

    def test_an_origin_only_preselected_is_a_suggestion(self):
        """Without the reference of the file, the only open line of the supplier
        for the product is preselected, but nobody decided it."""
        wizard = self._wizard()
        line = wizard.imported_products_ids
        self.assertTrue(line.match_source_id)
        self.assertFalse(line.match_source_trusted)
        wizard._import_edoc()
        fiscal_line = wizard.document_id.fiscal_line_ids
        self.assertEqual(fiscal_line.import_purchase_line_id, self.order.order_line)
        self.assertEqual(fiscal_line.import_origin_state, "suggested")
        self.assertEqual(fiscal_line.import_state, "matched")

    def test_the_origin_chosen_in_the_grid_is_a_decision(self):
        wizard = self._wizard()
        line = wizard.imported_products_ids
        source = line.match_source_id
        line.match_source_id = False
        line.match_source_id = source
        self.assertTrue(line.match_source_trusted)
        wizard._import_edoc()
        fiscal_line = wizard.document_id.fiscal_line_ids
        self.assertEqual(fiscal_line.import_origin_state, "resolved")

    def test_one_click_with_the_order_declared_makes_the_bill(self):
        """Everything resolves by itself when the supplier declared the order
        (a known product of the order, an origin without doubt): the bill is
        made in one click."""
        wizard = self._wizard(self._declared_xml())
        action = wizard.action_import_and_open_move()
        move = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(move.invoice_line_ids.purchase_line_id, self.order.order_line)

    def test_one_click_refuses_what_the_import_only_guessed(self):
        """A product and an origin that were only guessed wait for a person: the
        bill is refused, and goes through when the grid is confirmed."""
        wizard = self._wizard()
        with self.assertRaises(UserError) as caught:
            wizard.action_import_and_open_move()
        self.assertIn("not resolved yet", str(caught.exception))
        line = wizard.imported_products_ids
        line.product_confirmed = True
        with self.assertRaises(UserError) as caught:
            wizard.action_import_and_open_move()
        self.assertIn("Confirm Origins", str(caught.exception))
        source = line.match_source_id
        line.match_source_id = False
        line.match_source_id = source
        action = wizard.action_import_and_open_move()
        move = self.env["account.move"].browse(action["res_id"])
        self.assertEqual(move.invoice_line_ids.purchase_line_id, self.order.order_line)

    def test_an_importer_without_purchase_rights_still_imports(self):
        """The fiscal profile imports the file without access to the purchase
        orders: the suggestion of the origin reads them anyway."""
        importer = self.env["res.users"].create(
            {
                "name": "Fiscal importer",
                "login": "fiscal_importer_review",
                "groups_id": [
                    Command.set(
                        [
                            self.env.ref("base.group_user").id,
                            self.env.ref("l10n_br_fiscal.group_manager").id,
                            self.env.ref("l10n_br_nfe.group_manager").id,
                        ]
                    )
                ],
            }
        )
        wizard = self._wizard(self._declared_xml())
        wizard._import_edoc()
        line = wizard.document_id.fiscal_line_ids
        line.import_purchase_line_id = False
        line.import_origin_state = False
        line.with_user(importer)._suggest_import_origin()
        self.assertEqual(line.import_purchase_line_id, self.order.order_line)
