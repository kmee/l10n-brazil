# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase


class TestStockMoveFiscalQuantity(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.product = cls.env["product.product"].create(
            {"name": "Parafuso Sextavado 8mm", "type": "consu", "is_storable": True}
        )
        cls.move = cls.env["stock.move"].create(
            {
                "name": "Remessa de parafusos",
                "product_id": cls.product.id,
                "product_uom": cls.product.uom_id.id,
                "product_uom_qty": 5.0,
                "location_id": cls.env.ref("stock.stock_location_stock").id,
                "location_dest_id": cls.env.ref("stock.stock_location_customers").id,
            }
        )

    def test_fiscal_quantity_without_reservation(self):
        self.move._action_confirm()
        self.assertEqual(self.move.quantity, 0.0)
        self.assertEqual(self.move.fiscal_quantity, 5.0)

    def test_fiscal_quantity_with_reservation(self):
        self.move._action_confirm()
        self.move.quantity = 2.0
        self.assertEqual(self.move.fiscal_quantity, 2.0)
