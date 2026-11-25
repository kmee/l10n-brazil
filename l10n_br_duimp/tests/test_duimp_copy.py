# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.addons.l10n_br_duimp.tests.common import DuimpCommon


class TestDuimpCopy(DuimpCommon):
    def test_copy_keeps_items_and_taxes(self):
        declaration = self._create_declaracao()
        self.assertTrue(declaration.item_ids.tax_ids)
        self.assertTrue(declaration.item_ids.addition_deduction_ids)
        self.assertTrue(declaration.payment_ids)

        duplicate = declaration.copy()

        self.assertFalse(duplicate.number)
        self.assertEqual(len(duplicate.item_ids), len(declaration.item_ids))
        self.assertFalse(duplicate.item_ids & declaration.item_ids)
        self.assertEqual(
            sorted(duplicate.item_ids.mapped("item_number")),
            sorted(declaration.item_ids.mapped("item_number")),
        )
        self.assertEqual(
            len(duplicate.item_ids.tax_ids), len(declaration.item_ids.tax_ids)
        )
        self.assertFalse(duplicate.item_ids.tax_ids & declaration.item_ids.tax_ids)
        self.assertEqual(duplicate.item_ids.tax_ids.declaration_id, duplicate)
        self.assertEqual(
            len(duplicate.item_ids.addition_deduction_ids),
            len(declaration.item_ids.addition_deduction_ids),
        )
        self.assertEqual(
            duplicate.item_ids.addition_deduction_ids.declaration_id, duplicate
        )
        self.assertEqual(len(duplicate.payment_ids), len(declaration.payment_ids))
        self.assertFalse(duplicate.payment_ids & declaration.payment_ids)
        # the original keeps its own lines
        self.assertEqual(declaration.item_ids.tax_ids.declaration_id, declaration)
