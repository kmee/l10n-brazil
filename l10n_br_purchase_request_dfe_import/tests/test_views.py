# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestViews(TransactionCase):
    def _check_fields(self, model, node):
        for field in node.iterchildren():
            if field.tag != "field":
                self._check_fields(model, field)
                continue
            name = field.get("name")
            self.assertIn(name, self.env[model]._fields, f"{model}.{name}")
            comodel = self.env[model]._fields[name].comodel_name
            for sub in field.xpath("./tree|./form"):
                self._check_fields(comodel, sub)

    def test_every_field_of_the_views_exists_in_the_model(self):
        views = self.env["ir.ui.view"].search(
            [
                (
                    "id",
                    "in",
                    self.env["ir.model.data"]
                    .search(
                        [
                            ("module", "=", "l10n_br_purchase_request_dfe_import"),
                            ("model", "=", "ir.ui.view"),
                        ]
                    )
                    .mapped("res_id"),
                )
            ]
        )
        self.assertTrue(views)
        for view in views.filtered(lambda view: view.type in ("form", "tree")):
            arch = self.env[view.model].get_view(view.id)["arch"]
            self._check_fields(view.model, etree.fromstring(arch))
