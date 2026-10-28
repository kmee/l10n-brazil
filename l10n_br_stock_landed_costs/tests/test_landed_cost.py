# Copyright 2026 KMEE INFORMATICA LTDA - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLandedCostNetCost(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.env.user.company_ids += cls.company
        cls.env.user.company_id = cls.company
        cls.carrier = cls.env.ref("l10n_br_base.res_partner_intel")
        cls.carrier.tax_framework = "3"
        cls.fiscal_operation = cls.env.ref("l10n_br_fiscal.fo_compras")
        cls.fiscal_operation_line = cls.env.ref("l10n_br_fiscal.fo_compras_compras")
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )

        Account = cls.env["account.account"]
        cls.account_valuation, cls.account_stock_in, cls.account_stock_out = (
            Account.create(
                {
                    "name": name,
                    "code": code,
                    "account_type": "asset_current",
                    "company_id": cls.company.id,
                }
            )
            for name, code in (
                ("Stock valuation (test)", "TLCVAL"),
                ("Stock input (test)", "TLCIN"),
                ("Stock output (test)", "TLCOUT"),
            )
        )
        cls.journal = cls.env["account.journal"].create(
            {
                "name": "Landed costs (test)",
                "code": "TLCJ",
                "type": "general",
                "company_id": cls.company.id,
            }
        )
        cls.categ = cls.env["product.category"].create({"name": "Landed cost (test)"})
        cls.categ.with_company(cls.company).write(
            {
                "property_stock_account_input_categ_id": cls.account_stock_in.id,
                "property_stock_account_output_categ_id": cls.account_stock_out.id,
                "property_stock_valuation_account_id": cls.account_valuation.id,
                "property_stock_journal": cls.journal.id,
                "property_valuation": "real_time",
                "property_cost_method": "fifo",
            }
        )
        cls.company.write(
            {
                "stock_valuation_via_stock_price": True,
                "lc_journal_id": cls.journal.id,
            }
        )

        Product = cls.env["product.product"]
        goods = cls.env.ref("product.product_product_6")
        cls.goods_a = goods.copy(
            {"name": "Goods A (test)", "categ_id": cls.categ.id, "weight": 2.0}
        )
        cls.goods_a.volume = 1.0
        cls.goods_b = goods.copy(
            {"name": "Goods B (test)", "categ_id": cls.categ.id, "weight": 1.0}
        )
        cls.goods_b.volume = 3.0
        cls.cfop_freight = cls.env.ref("l10n_br_fiscal.cfop_1353")
        cls.document_number = 1000
        cls.freight = Product.create(
            {
                "name": "Freight (test)",
                "detailed_type": "service",
                "landed_cost_ok": True,
                "categ_id": cls.categ.id,
                "ncm_id": cls.env.ref("l10n_br_fiscal.ncm_00000000").id,
                "tax_icms_or_issqn": "icms",
            }
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _receive(self, lines, fiscal=True):
        """Receive ``lines`` as [(product, qty, price_unit)] in one picking."""
        picking_vals = {
            "picking_type_id": self.warehouse.in_type_id.id,
            "location_id": self.env.ref("stock.stock_location_suppliers").id,
            "location_dest_id": self.warehouse.lot_stock_id.id,
            "partner_id": self.carrier.id,
            "company_id": self.company.id,
        }
        if fiscal:
            picking_vals["fiscal_operation_id"] = self.fiscal_operation.id
        picking = self.env["stock.picking"].create(picking_vals)
        for product, qty, price in lines:
            move_vals = {
                "name": product.name,
                "picking_id": picking.id,
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": qty,
                "price_unit": price,
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
                "company_id": self.company.id,
                "partner_id": self.carrier.id,
            }
            if fiscal:
                move_vals.update(
                    {
                        "fiscal_operation_id": self.fiscal_operation.id,
                        "fiscal_operation_line_id": self.fiscal_operation_line.id,
                    }
                )
            self.env["stock.move"].create(move_vals)
        picking.action_confirm()
        picking.action_assign()
        for move_line in picking.move_ids.move_line_ids:
            move_line.qty_done = move_line.reserved_uom_qty
        picking.with_context(skip_immediate=True, skip_backorder=True).button_validate()
        self.assertEqual(picking.state, "done")
        return picking

    def _freight_document(self, amounts=(100.0,), product=None, operation=True):
        """An incoming CT-e with one line per amount.

        Without ``operation`` the lines look like an imported CT-e: the ICMS
        is stated, but there is no fiscal operation to derive its credit.
        """
        product = self.freight if product is None else product
        line_vals = []
        for amount in amounts:
            vals = {
                "name": "Freight",
                "product_id": product.id,
                "uom_id": self.env.ref("uom.product_uom_unit").id,
                "quantity": 1.0,
                "price_unit": amount,
            }
            if operation:
                vals.update(
                    {
                        "fiscal_operation_id": self.fiscal_operation.id,
                        "fiscal_operation_line_id": self.fiscal_operation_line.id,
                    }
                )
            else:
                vals.update(
                    {
                        "icms_cst_id": self.env.ref("l10n_br_fiscal.cst_icms_00").id,
                        "icms_base": amount,
                        "icms_percent": 12.0,
                        "icms_value": amount * 0.12,
                    }
                )
            line_vals.append(Command.create(vals))
        TestLandedCostNetCost.document_number += 1
        document = self.env["l10n_br_fiscal.document"].create(
            {
                "document_type_id": self.env.ref("l10n_br_fiscal.document_57").id,
                "fiscal_operation_id": operation and self.fiscal_operation.id,
                "fiscal_operation_type": "in",
                "issuer": "partner",
                "company_id": self.company.id,
                "partner_id": self.carrier.id,
                "document_serie": "1",
                "document_number": str(self.document_number),
                "fiscal_line_ids": line_vals,
            }
        )
        if operation:
            document.fiscal_line_ids.cfop_id = self.cfop_freight
        else:
            # As the CT-e import does.
            document.fiscal_operation_type = "in"
        return document

    def _create_landed_cost(self, document, pickings, split_method="by_quantity"):
        document.landed_cost_picking_ids = pickings
        document.landed_cost_split_method = split_method
        action = document.action_create_landed_cost()
        return self.env["stock.landed.cost"].browse(action["res_id"])

    def _allocated(self, landed_cost, product):
        return sum(
            landed_cost.valuation_adjustment_lines.filtered(
                lambda adj: adj.product_id == product
            ).mapped("additional_landed_cost")
        )

    # ------------------------------------------------------------------
    # Net cost: which tax of the freight reaches the stock
    # ------------------------------------------------------------------

    def test_creditable_icms_stays_out_of_stock(self):
        picking = self._receive([(self.goods_a, 1.0, 800.0)])
        stock_value = sum(picking.move_ids.stock_valuation_layer_ids.mapped("value"))
        document = self._freight_document()
        line = document.fiscal_line_ids

        landed_cost = self._create_landed_cost(document, picking)

        self.assertGreater(line.icms_value, 0.0)
        self.assertFalse(line.ipi_value)
        self.assertTrue(line.icms_tax_is_creditable)
        net = line.fiscal_amount_total - line.icms_value
        self.assertAlmostEqual(landed_cost.amount_total, net, places=2)
        self.assertEqual(landed_cost.fiscal_document_id, document)
        self.assertEqual(landed_cost.account_journal_id, self.journal)
        self.assertEqual(landed_cost.cost_lines.product_id, self.freight)
        self.assertEqual(landed_cost.cost_lines.account_id, self.account_stock_in)

        landed_cost.button_validate()

        # The valuation layer and the journal entry carry the same net amount.
        self.assertEqual(landed_cost.state, "done")
        layer_value = sum(landed_cost.stock_valuation_layer_ids.mapped("value"))
        self.assertAlmostEqual(layer_value, net, places=2)
        entry_lines = landed_cost.account_move_id.line_ids
        stock_debit = sum(
            entry_lines.filtered(
                lambda ln: ln.account_id == self.account_valuation
            ).mapped("debit")
        )
        input_credit = sum(
            entry_lines.filtered(
                lambda ln: ln.account_id == self.account_stock_in
            ).mapped("credit")
        )
        self.assertAlmostEqual(stock_debit, layer_value, places=2)
        self.assertAlmostEqual(input_credit, layer_value, places=2)
        self.assertAlmostEqual(
            self.goods_a.with_company(self.company).value_svl,
            stock_value + net,
            places=2,
        )

    def test_non_creditable_cst_keeps_icms_in_cost(self):
        picking = self._receive([(self.goods_a, 1.0, 800.0)])
        document = self._freight_document()
        line = document.fiscal_line_ids
        line.icms_cst_id = self.env.ref("l10n_br_fiscal.cst_icms_90")

        landed_cost = self._create_landed_cost(document, picking)

        self.assertGreater(line.icms_value, 0.0)
        self.assertFalse(line.icms_tax_is_creditable)
        self.assertAlmostEqual(
            landed_cost.amount_total, line.fiscal_amount_total, places=2
        )

    def test_simples_buyer_takes_no_credit(self):
        picking = self._receive([(self.goods_a, 1.0, 800.0)])
        document = self._freight_document()
        line = document.fiscal_line_ids
        # The CT-e states the ICMS of the carrier; the buyer is Simples.
        self.company.tax_framework = "1"

        landed_cost = self._create_landed_cost(document, picking)

        self.assertGreater(line.icms_value, 0.0)
        self.assertFalse(line.icms_tax_is_creditable)
        self.assertAlmostEqual(
            landed_cost.amount_total, line.fiscal_amount_total, places=2
        )

    def test_own_use_goods_keep_freight_tax_in_cost(self):
        picking = self._receive([(self.goods_a, 1.0, 800.0)])
        picking.move_ids.cfop_id = self.env.ref("l10n_br_fiscal.cfop_1556")
        document = self._freight_document()
        line = document.fiscal_line_ids
        self.assertTrue(line.icms_tax_is_creditable)

        landed_cost = self._create_landed_cost(document, picking)

        self.assertFalse(line.icms_tax_is_creditable)
        self.assertGreater(line.icms_value, 0.0)
        self.assertAlmostEqual(
            landed_cost.amount_total, line.fiscal_amount_total, places=2
        )

    def test_receipt_of_unknown_destination_keeps_freight_tax_in_cost(self):
        picking = self._receive([(self.goods_a, 1.0, 800.0)], fiscal=False)
        document = self._freight_document()
        line = document.fiscal_line_ids

        landed_cost = self._create_landed_cost(document, picking)

        self.assertGreater(line.icms_value, 0.0)
        self.assertFalse(line.icms_tax_is_creditable)
        self.assertAlmostEqual(
            landed_cost.amount_total, line.fiscal_amount_total, places=2
        )

    def test_company_valued_gross_allocates_gross(self):
        picking = self._receive([(self.goods_a, 1.0, 800.0)])
        self.company.stock_valuation_via_stock_price = False
        document = self._freight_document()
        line = document.fiscal_line_ids

        landed_cost = self._create_landed_cost(document, picking)

        self.assertGreater(line.icms_value, 0.0)
        self.assertTrue(line.icms_tax_is_creditable)
        self.assertAlmostEqual(
            landed_cost.amount_total, line.fiscal_amount_total, places=2
        )

    def test_line_without_operation_line_allocates_gross(self):
        picking = self._receive([(self.goods_a, 1.0, 800.0)])
        document = self._freight_document(amounts=(80.0,), operation=False)
        line = document.fiscal_line_ids

        landed_cost = self._create_landed_cost(document, picking)

        self.assertAlmostEqual(line.icms_value, 9.6, places=2)
        self.assertFalse(line.cost_unit)
        self.assertAlmostEqual(landed_cost.amount_total, 80.0, places=2)

    def test_line_copied_without_origin_is_derived(self):
        document = self._freight_document()
        line = self.env["l10n_br_fiscal.document.line"].create(
            {
                "document_id": document.id,
                "name": "Copied from a journal item without fiscal line",
                "creditability_origin": False,
            }
        )
        self.assertEqual(line.creditability_origin, "derived")

    # ------------------------------------------------------------------
    # Allocation among the receipts
    # ------------------------------------------------------------------

    def test_split_methods(self):
        # A: qty 1, weight 2, volume 1, value 800 net of ICMS.
        # B: qty 3, weight 1, volume 3, value 300 net of ICMS.
        picking = self._receive(
            [(self.goods_a, 1.0, 800.0), (self.goods_b, 3.0, 100.0)]
        )
        move_a = picking.move_ids.filtered(lambda m: m.product_id == self.goods_a)
        move_b = picking.move_ids - move_a
        value_a = sum(move_a.stock_valuation_layer_ids.mapped("value"))
        value_b = sum(move_b.stock_valuation_layer_ids.mapped("value"))
        shares = {
            "equal": (1, 1),
            "by_quantity": (1, 3),
            "by_weight": (2 * 1, 1 * 3),
            "by_volume": (1 * 1, 3 * 3),
            "by_current_cost_price": (value_a, value_b),
        }
        for method, (weight_a, weight_b) in shares.items():
            with self.subTest(method=method):
                document = self._freight_document()
                landed_cost = self._create_landed_cost(document, picking, method)
                net = landed_cost.amount_total
                self.assertEqual(landed_cost.cost_lines.split_method, method)
                expected_a = net * weight_a / (weight_a + weight_b)
                self.assertAlmostEqual(
                    self._allocated(landed_cost, self.goods_a), expected_a, places=2
                )
                self.assertAlmostEqual(
                    self._allocated(landed_cost, self.goods_b),
                    net - expected_a,
                    places=2,
                )

    def test_split_layers_agree_with_the_entry(self):
        picking_a = self._receive([(self.goods_a, 1.0, 800.0)])
        picking_b = self._receive([(self.goods_b, 3.0, 100.0)])
        document = self._freight_document(amounts=(60.0, 40.0))

        landed_cost = self._create_landed_cost(document, picking_a + picking_b)
        landed_cost.button_validate()

        self.assertEqual(len(landed_cost.cost_lines), 2)
        layers = landed_cost.stock_valuation_layer_ids
        self.assertEqual(layers.product_id, self.goods_a + self.goods_b)
        for product in (self.goods_a, self.goods_b):
            product_layers = layers.filtered_domain([("product_id", "=", product.id)])
            self.assertAlmostEqual(
                sum(product_layers.mapped("value")),
                self._allocated(landed_cost, product),
                places=2,
            )
        stock_debit = sum(
            landed_cost.account_move_id.line_ids.filtered(
                lambda ln: ln.account_id == self.account_valuation
            ).mapped("debit")
        )
        self.assertAlmostEqual(stock_debit, sum(layers.mapped("value")), places=2)
        self.assertAlmostEqual(stock_debit, landed_cost.amount_total, places=2)

    def test_split_method_defaults_to_the_cost_product(self):
        picking = self._receive([(self.goods_a, 1.0, 800.0)])
        self.freight.split_method_landed_cost = "by_weight"

        landed_cost = self._create_landed_cost(
            self._freight_document(), picking, split_method=False
        )

        self.assertEqual(landed_cost.cost_lines.split_method, "by_weight")

    # ------------------------------------------------------------------
    # Invalid requests
    # ------------------------------------------------------------------

    def test_no_receipt_selected(self):
        document = self._freight_document()
        with self.assertRaisesRegex(UserError, "receipts"):
            document.action_create_landed_cost()

    def test_zero_cost_line_is_skipped(self):
        picking = self._receive([(self.goods_a, 1.0, 800.0)])
        document = self._freight_document(amounts=(0.0, 100.0))

        landed_cost = self._create_landed_cost(document, picking)

        self.assertEqual(len(landed_cost.cost_lines), 1)
        self.assertGreater(landed_cost.amount_total, 0.0)

    def test_document_without_cost(self):
        picking = self._receive([(self.goods_a, 1.0, 800.0)])
        document = self._freight_document(amounts=(0.0,))
        with self.assertRaisesRegex(UserError, "No line"):
            self._create_landed_cost(document, picking)

    def test_line_without_product(self):
        picking = self._receive([(self.goods_a, 1.0, 800.0)])
        document = self._freight_document(product=self.env["product.product"])
        with self.assertRaisesRegex(UserError, "cost product"):
            self._create_landed_cost(document, picking)

    def test_company_without_journal(self):
        picking = self._receive([(self.goods_a, 1.0, 800.0)])
        self.company.lc_journal_id = False
        self.env["account.journal"].search(
            [("company_id", "=", self.company.id), ("type", "=", "general")]
        ).action_archive()
        with self.assertRaisesRegex(UserError, "journal"):
            self._create_landed_cost(self._freight_document(), picking)

    def test_outgoing_document_is_refused(self):
        picking = self._receive([(self.goods_a, 1.0, 800.0)])
        document = self._freight_document()
        document.fiscal_operation_type = "out"
        with self.assertRaisesRegex(UserError, "incoming"):
            self._create_landed_cost(document, picking)

    def test_cost_is_not_allocated_twice(self):
        picking = self._receive([(self.goods_a, 1.0, 800.0)])
        document = self._freight_document()
        first = self._create_landed_cost(document, picking)
        with self.assertRaisesRegex(UserError, "already has a landed cost"):
            document.action_create_landed_cost()

        first.button_cancel()
        second = self._create_landed_cost(document, picking)

        self.assertEqual(document.landed_cost_count, 2)
        self.assertNotEqual(first, second)

    def test_view_landed_costs(self):
        picking = self._receive([(self.goods_a, 1.0, 800.0)])
        document = self._freight_document()
        landed_cost = self._create_landed_cost(document, picking)

        action = document.action_view_landed_costs()

        self.assertEqual(document.landed_cost_count, 1)
        self.assertEqual(action["res_id"], landed_cost.id)
        self.assertEqual(action["domain"], [("fiscal_document_id", "=", document.id)])
