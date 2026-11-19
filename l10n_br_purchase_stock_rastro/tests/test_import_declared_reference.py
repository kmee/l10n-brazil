# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import tagged

from . import common


@tagged("post_install", "-at_install")
class TestImportDeclaredReference(common.ImportWizardCommon):
    """What the supplier declared (xPed and nItemPed) and what was decided on
    the import are two things: the second never rewrites the first, and a file
    imported again changes nothing in its document."""

    def _decided_xml(self):
        """The supplier declared an order that is not ours (xPed OC00589)."""
        return (
            self.xml.decode()
            .replace("</prod>", "<xPed>OC00589</xPed><nItemPed>7</nItemPed></prod>", 1)
            .encode()
        )

    def _choose_origin(self, wizard):
        line = wizard.imported_products_ids
        source = line.match_source_id
        self.assertTrue(source)
        line.match_source_id = False
        line.match_source_id = source
        line.product_confirmed = True

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

    def test_the_origin_does_not_overwrite_what_the_supplier_declared(self):
        wizard = self._wizard(self._decided_xml())
        self._choose_origin(wizard)
        wizard._import_edoc()
        line = wizard.document_id.fiscal_line_ids
        self.assertEqual(line.import_purchase_line_id, self.order.order_line)
        self.assertEqual(line.import_origin_state, "resolved")
        # the document keeps the xPed and the nItemPed as the supplier wrote them
        self.assertEqual(line.partner_order, "OC00589")
        self.assertEqual(line.partner_order_line, "7")
        self.assertEqual(line.nfe40_xPed, "OC00589")
        self.assertEqual(line.nfe40_nItemPed, "7")

    def test_a_file_without_reference_stays_without_reference(self):
        wizard = self._wizard()
        self._choose_origin(wizard)
        wizard._import_edoc()
        line = wizard.document_id.fiscal_line_ids
        self.assertEqual(line.import_purchase_line_id, self.order.order_line)
        self.assertFalse(line.partner_order)
        self.assertFalse(line.partner_order_line)
        self.assertFalse(line.nfe40_xPed)

    def test_the_bill_matches_the_receipt_through_the_decided_origin(self):
        """With the declared reference kept as the supplier wrote it, the bill
        is still matched with the receipt: through the order line decided."""
        wizard = self._wizard(self._decided_xml())
        self._choose_origin(wizard)
        action = wizard.action_import_and_open_move()
        move = self.env["account.move"].browse(action["res_id"])
        bill_line = move.invoice_line_ids
        self.assertEqual(bill_line.purchase_line_id, self.order.order_line)
        self.assertEqual(bill_line.partner_order, "OC00589")
        self.env.flush_all()  # the reference is read with SQL
        expr = self.env["account.move.line"]._get_bill_matching_reference_sql("aml")
        self.env.cr.execute(
            f"SELECT ({expr}) FROM account_move_line aml WHERE aml.id = %s",
            [bill_line.id],
        )
        self.assertEqual(self.env.cr.fetchone()[0], f"{self.order.name}-1")
        # the receipt of the order line has the same reference
        receipt = self.order.order_line.move_ids
        expr = self.env["stock.move"]._get_bill_matching_reference_sql("sm")
        self.env.cr.execute(
            f"SELECT ({expr}) FROM stock_move sm WHERE sm.id = %s", [receipt[0].id]
        )
        self.assertEqual(self.env.cr.fetchone()[0], f"{self.order.name}-1")
