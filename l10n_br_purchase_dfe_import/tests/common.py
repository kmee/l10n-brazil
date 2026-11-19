# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, fields

from odoo.addons.l10n_br_fiscal_dfe_import.tests.common import KEY_1, DfeImportCase


class PurchaseImportCase(DfeImportCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.unit = cls.env.ref("uom.product_uom_unit")
        cls.operation = cls.env.ref("l10n_br_fiscal.fo_compras")
        cls.product = cls.env["product.product"].create(
            {"name": "Reviewed product", "detailed_type": "consu"}
        )
        cls.Match = cls.env["l10n_br_purchase_dfe_import.match"]
        cls.document, _errors = cls.Document.dfe_import_files(
            [("nfe.xml", cls._xml(KEY_1))]
        )
        cls.document.fiscal_operation_id = cls.operation
        cls.line = cls.document.fiscal_line_ids
        cls.supplier = cls.document.partner_id

    def _order(self, quantity=10.0, price=140.0, confirm=True, partner=None):
        order = self.env["purchase.order"].create(
            {
                "partner_id": (partner or self.supplier).id,
                "company_id": self.company.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product.id,
                            "name": self.product.name,
                            "product_qty": quantity,
                            "product_uom": self.unit.id,
                            "price_unit": price,
                            "date_planned": fields.Datetime.now(),
                        }
                    )
                ],
            }
        )
        if confirm:
            order.button_confirm()
        return order

    def _resolve_product(self, line=None):
        (line or self.line)._apply_import_depara(
            product=self.product, uom=self.unit, fiscal_operation=self.operation
        )

    def _rows(self, **domain):
        # the read model is SQL: what the test wrote has to reach the database
        self.env.flush_all()
        self.env.invalidate_all()
        return self.Match.search([(key, "=", value) for key, value in domain.items()])
