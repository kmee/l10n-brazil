# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import importlib.util
import os

from odoo import Command
from odoo.modules.module import get_module_path
from odoo.tests.common import TransactionCase


class TestImportStateMigration(TransactionCase):
    """The lines that the old import wizard left have no state: they are resolved."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

    def _migrate(self):
        path = os.path.join(
            get_module_path("l10n_br_fiscal_edi"),
            "migrations",
            "18.0.3.10.0",
            "post-migration.py",
        )
        spec = importlib.util.spec_from_file_location("edi_post_migration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.env["l10n_br_fiscal.document.line"].flush_model()
        self.env["l10n_br_fiscal.document"].flush_model()
        module.migrate(self.env.cr, "18.0.3.9.0")
        self.env["l10n_br_fiscal.document.line"].invalidate_model()
        self.env["l10n_br_fiscal.document"].invalidate_model()

    def _document(self, imported):
        return self.env["l10n_br_fiscal.document"].create(
            {
                "document_type_id": self.env.ref("l10n_br_fiscal.document_55").id,
                "fiscal_operation_id": self.env.ref("l10n_br_fiscal.fo_compras").id,
                "imported_document": imported,
                "partner_id": self.env.ref("l10n_br_base.res_partner_akretion").id,
                "company_id": self.env.company.id,
                "fiscal_line_ids": [
                    Command.create(
                        {
                            "name": "Item",
                            "quantity": 1.0,
                            "price_unit": 10.0,
                            "uom_id": self.env.ref("uom.product_uom_unit").id,
                        }
                    )
                ],
            }
        )

    def _forget_state(self, document):
        """Leave the document as the old wizard did: no state, on it or its lines."""
        document.flush_recordset()
        document.fiscal_line_ids.flush_recordset()
        self.env.cr.execute(
            "UPDATE l10n_br_fiscal_document SET import_state = NULL WHERE id = %s",
            (document.id,),
        )
        self.env.cr.execute(
            "UPDATE l10n_br_fiscal_document_line SET import_state = NULL "
            "WHERE document_id = %s",
            (document.id,),
        )
        document.invalidate_recordset()
        document.fiscal_line_ids.invalidate_recordset()

    def test_the_lines_of_an_old_imported_document_are_resolved(self):
        old = self._document(imported=True)
        self._forget_state(old)
        typed = self._document(imported=False)
        reviewed = self._document(imported=True)
        reviewed.fiscal_line_ids.import_state = "pending"
        self.assertFalse(old.fiscal_line_ids.import_state)
        self.assertFalse(old.import_state)
        self._migrate()
        self.assertEqual(old.fiscal_line_ids.import_state, "resolved")
        self.assertEqual(old.import_state, "resolved")
        # what a person is still reviewing, and what was not imported, is left alone
        self.assertEqual(reviewed.fiscal_line_ids.import_state, "pending")
        self.assertEqual(reviewed.import_state, "pending")
        self.assertFalse(typed.fiscal_line_ids.import_state)
        self.assertFalse(typed.import_state)
        # it can run again
        self._migrate()
        self.assertEqual(old.fiscal_line_ids.import_state, "resolved")
        self.assertEqual(old.import_state, "resolved")
        self.assertEqual(reviewed.fiscal_line_ids.import_state, "pending")
