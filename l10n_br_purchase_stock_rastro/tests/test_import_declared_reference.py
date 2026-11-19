# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import tagged

from . import common


@tagged("post_install", "-at_install")
class TestImportDeclaredReference(common.ImportWizardCommon):
    """What the supplier declared (xPed and nItemPed) and what was decided on
    the import are two things: the second never rewrites the first, and a file
    imported again changes nothing in its document."""

    def test_reimporting_the_file_changes_nothing_that_was_decided(self):
        wizard = self._wizard()
        wizard._import_edoc()
        document = wizard.document_id
        line = document.fiscal_line_ids
        self.assertEqual(line.import_origin_state, "suggested")
        document.action_confirm_import_origins()
        line.action_resolve_line()
        self.assertEqual(line.import_origin_state, "resolved")
        self.assertEqual(line.import_state, "resolved")

        again = self._wizard()
        _binding, same = again._import_edoc()
        self.assertEqual(same, document)
        self.assertEqual(line.import_origin_state, "resolved")
        self.assertEqual(line.import_state, "resolved")
        self.assertEqual(line.import_purchase_line_id, self.order.order_line)
