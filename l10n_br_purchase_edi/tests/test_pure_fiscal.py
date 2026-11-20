# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.tests import tagged

from .common import PurchaseEdiCase


@tagged("post_install", "-at_install")
class TestPureFiscalUser(PurchaseEdiCase):
    """A user of the fiscal group only, with no right on purchases, accounting or
    stock, reads, edits and confirms the imported document while orders exist."""

    def _as_pure_fiscal(self, document):
        user = self._fiscal_user("pure-fiscal")
        # what the tests wrote must reach the database, and the cache of the
        # superuser must not hide a read the user has no right to do
        self.env.flush_all()
        self.env.invalidate_all()
        return document.with_user(user).with_context(
            allowed_company_ids=user.company_ids.ids
        )

    def _read_everything(self, document):
        document.get_view(view_type="form")
        line_model = document.fiscal_line_ids
        line_view = line_model.get_view(view_type="form")
        self.assertTrue(etree.fromstring(line_view["arch"]) is not None)
        document.read(list(document.fields_get()))
        line_model.read(list(line_model.fields_get()))

    def _open_data(self):
        """An open order of the supplier, the origin suggested and resolved."""
        self._order()
        self._resolve_product()
        self.assertTrue(self.line.import_purchase_line_id)

    def test_the_pure_fiscal_user_reads_edits_and_saves(self):
        self._open_data()
        document = self._as_pure_fiscal(self.document)

        self._read_everything(document)
        document.fiscal_line_ids.write({"name": "Edited by the fiscal user"})
        document.fiscal_line_ids.write({"quantity": 2.0})
        self.env.flush_all()
        self._read_everything(document)

    def test_the_pure_fiscal_user_confirms_the_origins_and_the_suggestions(self):
        self._open_data()
        document = self._as_pure_fiscal(self.document)

        document.action_confirm_import_origins()
        document.action_import_confirm_suggestions()
        self.env.flush_all()

        self.assertEqual(self.line.import_origin_state, "resolved")
        self._read_everything(document)

    def test_the_pure_fiscal_user_changes_the_origin_of_a_line(self):
        self._open_data()
        document = self._as_pure_fiscal(self.document)

        document.fiscal_line_ids.write({"import_purchase_line_id": False})
        document.fiscal_line_ids._suggest_import_origin()
        self.env.flush_all()
        self._read_everything(document)
