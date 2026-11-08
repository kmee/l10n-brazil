# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_br_fiscal.tests.tools import get_undefined_view_fields


@tagged("post_install", "-at_install")
class TestPickingView(TransactionCase):
    def test_get_view_move_fields(self):
        """Every field injected from the fiscal line mixin form must exist on
        stock.move (e.g. fields only defined on the fiscal document line,
        like ref_document_item from l10n_br_nfe)."""
        company = self.env.ref("l10n_br_base.empresa_lucro_presumido")
        picking = self.env["stock.picking"].with_company(company)
        arch, _view = picking._get_view(view_type="form")
        self.assertTrue(
            arch.xpath("//field[@name='move_ids_without_package']//field"),
            "No move fields in the picking form.",
        )
        self.assertTrue(
            arch.xpath("//field[@name='fiscal_operation_line_id']"),
            "Fiscal fields were not injected into the picking form.",
        )
        self.assertFalse(get_undefined_view_fields(self.env, "stock.picking", arch))

    def test_get_view_move_form_fields(self):
        """Same check on the stock.move form, where the mixin form is
        injected by the mixin itself."""
        company = self.env.ref("l10n_br_base.empresa_lucro_presumido")
        move = self.env["stock.move"].with_company(company)
        arch, _view = move._get_view(view_type="form")
        self.assertFalse(get_undefined_view_fields(self.env, "stock.move", arch))
