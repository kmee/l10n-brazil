# Copyright (C) 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase

# What each demo company may recover on a purchase, and therefore what the
# net acquisition cost becomes on a 800.00 purchase carrying 96.00 of
# embedded ICMS and 26.00 of added IPI (fiscal total 826.00).
#
# Both are industries, so both credit IPI. What separates them is PIS and
# COFINS: they only exist in the non cumulative regime (Leis 10.637/2002 and
# 10.833/2003, art. 3), so Lucro Presumido keeps them in the cost.
COMPANY_EXPECTATION = {
    "l10n_br_base.empresa_lucro_real": {
        "credits": ("icms", "ipi", "pis", "cofins"),
        "label": "Lucro Real",
    },
    "l10n_br_base.empresa_lucro_presumido": {
        "credits": ("icms", "ipi"),
        "label": "Lucro Presumido",
    },
}

# How each product category configuration reacts to the net cost.
#
# * FIFO and average read the price the move carries, so the net cost
#   reaches both the layer and the ledger;
# * standard prices the layer from the product standard price, so the core
#   drops the move price;
# * periodic inventory posts no entry on receipt, so the net cost abstains
#   and the layer keeps the gross cost, which is what keeps the stock report
#   and the ledger stating the same number.
CATEGORY_CASES = [
    ("fifo", "real_time", "net", True),
    ("average", "real_time", "net", True),
    ("standard", "real_time", "standard_price", True),
    ("fifo", "manual_periodic", "gross", False),
]


class TestNetCostCompanyMatrix(TransactionCase):
    """Both demo companies buying, across product category configurations.

    Crosses the two axes that decide the number: the buyer tax regime, which
    says which taxes are recoverable, and the product category, which says
    whether the net cost reaches the accounts at all. Each case asserts the
    valuation layer AND the journal entry, because a layer that is right
    while the entry is wrong is the failure this whole feature is about.
    """

    _case_seq = 0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.supplier = cls.env.ref("l10n_br_base.res_partner_intel")
        cls.supplier.tax_framework = "3"  # Normal, so it does highlight ICMS
        cls.fiscal_operation = cls.env.ref("l10n_br_fiscal.fo_compras")
        cls.fiscal_operation_line = cls.env.ref("l10n_br_fiscal.fo_compras_compras")
        cls.source_product = cls.env.ref("product.product_product_6")

        cls.companies = {}
        for xml_id in COMPANY_EXPECTATION:
            company = cls.env.ref(xml_id)
            company.is_industry = True
            cls.env.user.company_ids += company
            cls.companies[xml_id] = company

    def _prepare(self, company, cost_method, valuation):
        """A product of its own, in a category configured for this case.

        Both the average cost and the standard price are weighted over what
        is already in stock, so sharing a product between cases would make
        the assertions depend on the order the tests happen to run in.
        """
        # A short unique tag: journal codes are limited and truncating a
        # descriptive one collided between cases.
        type(self)._case_seq += 1
        suffix = f"{type(self)._case_seq:02d}"
        accounts = {}
        for key, name in (
            ("valuation", "Stock valuation"),
            ("bridge", "Stock input bridge"),
            ("expense", "Stock expense"),
        ):
            accounts[key] = self.env["account.account"].create(
                {
                    "name": f"{name} ({suffix})",
                    "code": f"MX{key[:1].upper()}{suffix}",
                    "account_type": "asset_current",
                    "company_id": company.id,
                }
            )
        journal = self.env["account.journal"].create(
            {
                "name": f"Stock journal ({suffix})",
                "code": f"MXJ{suffix}",
                "type": "general",
                "company_id": company.id,
            }
        )
        product = self.source_product.copy({"name": f"Net cost matrix {suffix}"})
        product.categ_id = self.env["product.category"].create(
            {"name": f"Net cost matrix {suffix}"}
        )
        product.categ_id.with_company(company).write(
            {
                "property_stock_account_input_categ_id": accounts["bridge"].id,
                "property_stock_account_output_categ_id": accounts["bridge"].id,
                "property_stock_valuation_account_id": accounts["valuation"].id,
                "property_stock_journal": journal.id,
                "property_valuation": valuation,
                "property_cost_method": cost_method,
            }
        )
        company.stock_valuation_via_stock_price = True
        return product, accounts

    def _receive(self, company, product, price_unit=800.0):
        warehouse = self.env["stock.warehouse"].search(
            [("company_id", "=", company.id)], limit=1
        )
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": warehouse.in_type_id.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": warehouse.lot_stock_id.id,
                "partner_id": self.supplier.id,
                "company_id": company.id,
                "fiscal_operation_id": self.fiscal_operation.id,
            }
        )
        move = self.env["stock.move"].create(
            {
                "name": product.name,
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": 1.0,
                "price_unit": price_unit,
                "company_id": company.id,
                "partner_id": self.supplier.id,
                "picking_id": picking.id,
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
                "fiscal_operation_id": self.fiscal_operation.id,
                "fiscal_operation_line_id": self.fiscal_operation_line.id,
            }
        )
        picking.action_confirm()
        picking.action_assign()
        for line in picking.move_ids.move_line_ids:
            line.qty_done = line.reserved_uom_qty
        picking.with_context(skip_immediate=True, skip_backorder=True).button_validate()
        return move

    def _expected_net_cost(self, move, credits):
        """The fiscal total minus what this company may recover."""
        expected = move.fiscal_amount_total
        for domain in credits:
            expected -= move[f"{domain}_value"]
        return expected

    def test_company_by_category_matrix(self):
        for xml_id, expectation in COMPANY_EXPECTATION.items():
            company = self.companies[xml_id]
            for cost_method, valuation, expected_kind, posts in CATEGORY_CASES:
                with self.subTest(
                    company=expectation["label"],
                    cost_method=cost_method,
                    valuation=valuation,
                ):
                    product, accounts = self._prepare(company, cost_method, valuation)
                    if expected_kind == "standard_price":
                        product.with_company(company).standard_price = 500.0

                    move = self._receive(company, product)
                    layer = move.stock_valuation_layer_ids
                    self.assertTrue(layer, "the receipt should be valued")

                    net = self._expected_net_cost(move, expectation["credits"])
                    if expected_kind == "net":
                        self.assertAlmostEqual(move.cost_unit, net, places=2)
                        self.assertAlmostEqual(layer.unit_cost, net, places=2)
                        self.assertLess(layer.unit_cost, move.price_unit)
                    elif expected_kind == "standard_price":
                        self.assertAlmostEqual(layer.unit_cost, 500.0, places=2)
                    else:
                        self.assertAlmostEqual(
                            layer.unit_cost, move.price_unit, places=2
                        )

                    self._assert_accounting(layer, accounts, posts)

    def _assert_accounting(self, layer, accounts, posts):
        """The entry states the same amount the layer does, or none at all."""
        entry = layer.account_move_id
        if not posts:
            self.assertFalse(entry, "periodic inventory posts nothing on receipt")
            return

        self.assertTrue(entry, "perpetual inventory should post an entry")
        debit = entry.line_ids.filtered(
            lambda line: line.account_id == accounts["valuation"]
        )
        credit = entry.line_ids.filtered(
            lambda line: line.account_id == accounts["bridge"]
        )
        self.assertAlmostEqual(debit.debit, layer.value, places=2)
        self.assertAlmostEqual(credit.credit, layer.value, places=2)
        self.assertAlmostEqual(sum(entry.line_ids.mapped("balance")), 0.0, places=2)

    def test_the_two_regimes_reach_different_costs(self):
        """The same purchase costs less for the company that recovers more.

        Stated as a comparison so the test says what the feature is for: a
        non cumulative buyer recovers PIS and COFINS on top of ICMS and IPI,
        and its inventory is worth less for the same invoice.
        """
        costs = {}
        for xml_id, expectation in COMPANY_EXPECTATION.items():
            company = self.companies[xml_id]
            product, _accounts = self._prepare(company, "fifo", "real_time")
            move = self._receive(company, product)
            costs[expectation["label"]] = move.cost_unit
            self.assertAlmostEqual(
                move.cost_unit,
                self._expected_net_cost(move, expectation["credits"]),
                places=2,
            )

        self.assertLess(
            costs["Lucro Real"],
            costs["Lucro Presumido"],
            "the non cumulative buyer recovers more, so its cost is lower",
        )
