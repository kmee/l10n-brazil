# Copyright 2026 KMEE INFORMATICA LTDA - Luis Felipe Mileo
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged

from odoo.addons.l10n_br_duimp.tests.common import (
    PRODUCT_CODE_1,
    PRODUCT_CODE_2,
    duimp_fake_payload,
    grant_nfe_access,
)

# Items of duimp_fake_payload: customs value 5300.00 for 100 units of item 1
# (II 16% = 848.00) and 4950.00 for 40 units of item 2 (II 14% = 693.00).
CUSTOMS_VALUE_1 = 5300.0
CUSTOMS_VALUE_2 = 4950.0
TOTAL_CUSTOMS_VALUE = CUSTOMS_VALUE_1 + CUSTOMS_VALUE_2


@tagged("post_install", "-at_install")
class TestDuimpLandedCost(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_real")
        cls.env.user.company_ids += cls.company
        cls.env.user.company_id = cls.company
        cls.env = cls.env(
            context=dict(cls.env.context, allowed_company_ids=cls.company.ids)
        )
        grant_nfe_access(cls.env)
        cls.warehouse = cls.env["stock.warehouse"].search(
            [("company_id", "=", cls.company.id)], limit=1
        )
        cls.fiscal_operation = cls.env.ref("l10n_br_fiscal.fo_compras")
        cls.unit = cls.env.ref("uom.product_uom_unit")

        Account = cls.env["account.account"]
        cls.account_valuation, cls.account_stock_in, cls.account_stock_out = (
            Account.create(
                {
                    "name": name,
                    "code": code,
                    "account_type": "asset_current",
                    "company_ids": [Command.set(cls.company.ids)],
                }
            )
            for name, code in (
                ("Stock valuation (test)", "TDLCVAL"),
                ("Stock input (test)", "TDLCIN"),
                ("Stock output (test)", "TDLCOUT"),
            )
        )
        journal = cls.env["account.journal"].create(
            {
                "name": "DUIMP landed costs (test)",
                "code": "TDLC",
                "type": "general",
                "company_id": cls.company.id,
            }
        )
        categ = cls.env["product.category"].create({"name": "Imported (test)"})
        categ.with_company(cls.company).write(
            {
                "property_stock_account_input_categ_id": cls.account_stock_in.id,
                "property_stock_account_output_categ_id": cls.account_stock_out.id,
                "property_stock_valuation_account_id": cls.account_valuation.id,
                "property_stock_journal": journal.id,
                "property_valuation": "real_time",
                "property_cost_method": "fifo",
            }
        )
        cls.company.write({"landed_cost_net_cost": True, "lc_journal_id": journal.id})

        # II and IPI come from the NCM; the ICMS of the import is configured
        # on the operation line, as a company does for its imports.
        ncm_1 = cls.env.ref("l10n_br_fiscal.ncm_22030000")
        ncm_1.write(
            {
                "tax_ii_id": cls.env.ref("l10n_br_fiscal.tax_ii_16").id,
                "tax_ipi_id": cls.env.ref("l10n_br_fiscal.tax_ipi_10").id,
            }
        )
        ncm_2 = cls.env.ref("l10n_br_fiscal.ncm_22011000")
        ncm_2.write(
            {
                "tax_ii_id": cls.env.ref("l10n_br_fiscal.tax_ii_14").id,
                "tax_ipi_id": cls.env.ref("l10n_br_fiscal.tax_ipi_5").id,
            }
        )
        cls.import_operation_line = cls.env["l10n_br_fiscal.operation.line"].create(
            {
                "fiscal_operation_id": cls.fiscal_operation.id,
                "name": "Import (test)",
                "tax_icms_or_issqn": "icms",
                "cfop_internal_id": cls.env.ref("l10n_br_fiscal.cfop_1102").id,
                "cfop_external_id": cls.env.ref("l10n_br_fiscal.cfop_2102").id,
                "cfop_export_id": cls.env.ref("l10n_br_fiscal.cfop_3102").id,
                "state": "approved",
                "tax_definition_ids": [
                    Command.create(
                        {
                            "tax_group_id": cls.env.ref(
                                "l10n_br_fiscal.tax_group_icms"
                            ).id,
                            "tax_id": cls.env.ref("l10n_br_fiscal.tax_icms_18").id,
                            "cst_id": cls.env.ref("l10n_br_fiscal.cst_icms_00").id,
                            "is_taxed": True,
                            "is_debit_credit": True,
                            "custom_tax": True,
                            "state": "approved",
                        }
                    )
                ],
            }
        )

        Product = cls.env["product.product"]
        cls.product_1 = Product.create(
            {
                "name": "Imported bearing (test)",
                "default_code": PRODUCT_CODE_1,
                "type": "consu",
                "is_storable": True,
                "categ_id": categ.id,
                "ncm_id": ncm_1.id,
            }
        )
        cls.product_2 = Product.create(
            {
                "name": "Imported sensor (test)",
                "default_code": PRODUCT_CODE_2,
                "type": "consu",
                "is_storable": True,
                "categ_id": categ.id,
                "ncm_id": ncm_2.id,
            }
        )
        cls.broker_service = Product.create(
            {
                "name": "Customs broker (test)",
                "type": "service",
                "landed_cost_ok": True,
                "categ_id": categ.id,
                "tax_icms_or_issqn": "issqn",
            }
        )
        cls.freight = Product.create(
            {
                "name": "Freight from the port (test)",
                "type": "service",
                "landed_cost_ok": True,
                "categ_id": categ.id,
                "ncm_id": cls.env.ref("l10n_br_fiscal.ncm_00000000").id,
                "tax_icms_or_issqn": "icms",
            }
        )

        cls.exporter = cls.env["res.partner"].create(
            {
                "name": "Exporter GmbH (test)",
                "is_company": True,
                "country_id": cls.env.ref("base.de").id,
            }
        )
        cls.broker = cls.env["res.partner"].create(
            {
                "name": "Customs broker Ltda (test)",
                "is_company": True,
                "country_id": cls.env.ref("base.br").id,
                "state_id": cls.company.state_id.id,
                "city_id": cls.company.city_id.id,
                "tax_framework": "3",
            }
        )
        cls.carrier = cls.env.ref("l10n_br_base.res_partner_intel")
        cls.carrier.tax_framework = "3"

        dados_gerais, itens = duimp_fake_payload()
        cls.declaration = cls.env["l10n_br_duimp.declaration"].create(
            {
                "number": dados_gerais["identificacao"]["numero"],
                "company_id": cls.company.id,
                "fiscal_operation_id": cls.fiscal_operation.id,
                "partner_id": cls.exporter.id,
            }
        )
        cls.declaration._import_from_payload(dados_gerais, itens)
        cls.declaration.item_ids.cfop_id = cls.env.ref("l10n_br_fiscal.cfop_3102")
        cls.declaration.action_open()
        cls.item_1 = cls.declaration.item_ids.filtered(lambda i: i.item_number == "1")
        cls.item_2 = cls.declaration.item_ids - cls.item_1
        cls.document_number = 7000

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _receive(self, product, quantity, price_unit, validate=True):
        picking = self.env["stock.picking"].create(
            {
                "picking_type_id": self.warehouse.in_type_id.id,
                "location_id": self.env.ref("stock.stock_location_suppliers").id,
                "location_dest_id": self.warehouse.lot_stock_id.id,
                "partner_id": self.exporter.id,
                "company_id": self.company.id,
                "fiscal_operation_id": self.fiscal_operation.id,
            }
        )
        self.env["stock.move"].create(
            {
                "name": product.name,
                "picking_id": picking.id,
                "product_id": product.id,
                "product_uom": product.uom_id.id,
                "product_uom_qty": quantity,
                "price_unit": price_unit,
                "location_id": picking.location_id.id,
                "location_dest_id": picking.location_dest_id.id,
                "company_id": self.company.id,
                "partner_id": self.exporter.id,
                "fiscal_operation_id": self.fiscal_operation.id,
                "fiscal_operation_line_id": self.import_operation_line.id,
            }
        )
        picking.action_confirm()
        if validate:
            picking.action_assign()
            picking.move_ids.quantity = quantity
            picking.move_ids.picked = True
            picking.with_context(skip_backorder=True).button_validate()
            self.assertEqual(picking.state, "done")
        return picking

    def _receive_items(self):
        """Receive each DUIMP item in its own receipt, at its customs value."""
        return [
            self._receive(item.product_id, item.quantity, value / item.quantity)
            for item, value in (
                (self.item_1, CUSTOMS_VALUE_1),
                (self.item_2, CUSTOMS_VALUE_2),
            )
        ]

    def _link_wizard(self):
        action = self.declaration.action_link_receipts()
        return self.env[action["res_model"]].browse(action["res_id"])

    def _link_receipts(self):
        pickings = self._receive_items()
        self._link_wizard().action_confirm()
        return pickings

    def _expense_document(self, document_type, partner, product, line, amount):
        TestDuimpLandedCost.document_number += 1
        return self.env["l10n_br_fiscal.document"].create(
            {
                "document_type_id": self.env.ref(document_type).id,
                "fiscal_operation_id": self.fiscal_operation.id,
                "fiscal_operation_type": "in",
                "issuer": "partner",
                "company_id": self.company.id,
                "partner_id": partner.id,
                "document_serie": "1",
                "document_number": str(self.document_number),
                "fiscal_line_ids": [
                    Command.create(
                        {
                            "name": product.name,
                            "product_id": product.id,
                            "uom_id": self.unit.id,
                            "quantity": 1.0,
                            "price_unit": amount,
                            "fiscal_operation_id": self.fiscal_operation.id,
                            "fiscal_operation_line_id": line.id,
                        }
                    )
                ],
            }
        )

    def _broker_nfse(self):
        return self._expense_document(
            "l10n_br_fiscal.document_SE",
            self.broker,
            self.broker_service,
            self.env.ref("l10n_br_fiscal.fo_compras_servico"),
            1000.0,
        )

    def _freight_cte(self):
        document = self._expense_document(
            "l10n_br_fiscal.document_57",
            self.carrier,
            self.freight,
            self.env.ref("l10n_br_fiscal.fo_compras_compras"),
            300.0,
        )
        document.fiscal_line_ids.cfop_id = self.env.ref("l10n_br_fiscal.cfop_1353")
        return document

    # ------------------------------------------------------------------
    # End to end
    # ------------------------------------------------------------------

    def test_end_to_end(self):
        # DUIMP -> incoming fiscal document, one line per item. The vendor bill
        # is left out: it needs a chart of accounts the landed cost does not.
        document = self.declaration._create_fiscal_document()
        self.assertEqual(
            document.fiscal_line_ids.duimp_item_id, self.item_1 + self.item_2
        )
        self.assertEqual(document.fiscal_line_ids.mapped("ii_value"), [848.0, 693.0])

        # Two receipts, valued by the standard Odoo price of the move: the 16.0
        # net cost stack (valuation at the net acquisition cost, OCA #4965 to
        # #4970) is not in 18.0, see the ROADMAP. The II is still computed on
        # the receipt line, from the NCM.
        receipts = self._receive_items()
        for picking, customs_value, ii_value in zip(
            receipts, (CUSTOMS_VALUE_1, CUSTOMS_VALUE_2), (848.0, 693.0), strict=True
        ):
            move = picking.move_ids
            self.assertAlmostEqual(move.ii_value, ii_value, places=2)
            layer_value = sum(move.stock_valuation_layer_ids.mapped("value"))
            self.assertAlmostEqual(layer_value, customs_value, places=2)

        # The receipts are linked to the DUIMP items by a suggestion the user
        # confirms.
        wizard = self._link_wizard()
        self.assertEqual(wizard.line_ids.item_id, self.item_1 + self.item_2)
        self.assertTrue(all(wizard.line_ids.mapped("suggested")))
        self.assertEqual(
            wizard.line_ids.move_id, receipts[0].move_ids + receipts[1].move_ids
        )
        wizard.action_confirm()
        self.assertEqual(self.item_1.move_ids, receipts[0].move_ids)
        self.assertFalse(self.declaration.item_ids.filtered("receipt_pending"))
        self.assertEqual(self.declaration.picking_count, 2)
        self.assertEqual(
            self.declaration.action_view_receipts()["domain"],
            [("id", "in", self.declaration.picking_ids.ids)],
        )

        # Customs expenses: the ISS of the broker stays in the cost, its PIS
        # and COFINS are credits; the ICMS, PIS and COFINS of the CT-e too.
        nfse, cte = self._broker_nfse(), self._freight_cte()
        nfse_line, cte_line = nfse.fiscal_line_ids, cte.fiscal_line_ids
        self.assertAlmostEqual(nfse_line.issqn_value, 50.0, places=2)
        self.assertAlmostEqual(
            nfse_line._get_landed_cost_amount(),
            1000.0 - nfse_line.pis_value - nfse_line.cofins_value,
            places=2,
        )
        self.assertAlmostEqual(nfse_line._get_landed_cost_amount(), 907.5, places=2)
        self.assertAlmostEqual(
            cte_line._get_landed_cost_amount(),
            300.0 - cte_line.icms_value - cte_line.pis_value - cte_line.cofins_value,
            places=2,
        )
        self.assertAlmostEqual(cte_line._get_landed_cost_amount(), 218.25, places=2)

        stock_before = {
            product: product.with_company(self.company).value_svl
            for product in (self.product_1, self.product_2)
        }
        self.declaration.expense_document_ids = nfse + cte
        action = self.declaration.action_create_landed_costs()
        landed_costs = self.declaration.landed_cost_ids
        self.assertEqual(action["domain"], [("id", "in", landed_costs.ids)])
        self.assertEqual(landed_costs.fiscal_document_id, nfse + cte)
        self.assertEqual(nfse.landed_cost_split_method, "by_customs_value")

        allocated = dict.fromkeys((self.product_1, self.product_2), 0.0)
        for landed_cost in landed_costs:
            self.assertEqual(landed_cost.cost_lines.split_method, "by_customs_value")
            self.assertEqual(landed_cost.picking_ids, receipts[0] + receipts[1])
            amount = landed_cost.amount_total
            adjustment_1 = landed_cost.valuation_adjustment_lines.filtered(
                lambda adj: adj.product_id == self.product_1
            )
            adjustment_2 = landed_cost.valuation_adjustment_lines - adjustment_1
            self.assertEqual(adjustment_1.customs_value, CUSTOMS_VALUE_1)
            self.assertEqual(adjustment_2.customs_value, CUSTOMS_VALUE_2)
            share_1 = round(amount * CUSTOMS_VALUE_1 / TOTAL_CUSTOMS_VALUE, 2)
            self.assertAlmostEqual(
                adjustment_1.additional_landed_cost, share_1, places=2
            )
            self.assertAlmostEqual(
                adjustment_2.additional_landed_cost, amount - share_1, places=2
            )

            landed_cost.button_validate()

            layers = landed_cost.stock_valuation_layer_ids
            self.assertAlmostEqual(sum(layers.mapped("value")), amount, places=2)
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
            self.assertAlmostEqual(stock_debit, amount, places=2)
            self.assertAlmostEqual(input_credit, amount, places=2)
            for adjustment in landed_cost.valuation_adjustment_lines:
                allocated[adjustment.product_id] += adjustment.additional_landed_cost

        # The two expenses are allocated in full: 907.50 + 218.25.
        self.assertAlmostEqual(sum(landed_costs.mapped("amount_total")), 1125.75, 2)
        self.assertAlmostEqual(sum(allocated.values()), 1125.75, places=2)
        self.assertAlmostEqual(allocated[self.product_1], 469.24 + 112.85, places=2)
        for product, value in allocated.items():
            self.assertAlmostEqual(
                product.with_company(self.company).value_svl,
                stock_before[product] + value,
                places=2,
            )

    # ------------------------------------------------------------------
    # Link to the receipts
    # ------------------------------------------------------------------

    def test_item_without_receipt_stays_pending(self):
        receipt = self._receive(self.product_1, 100.0, 53.0)
        wizard = self._link_wizard()

        line_2 = wizard.line_ids.filtered(lambda line: line.item_id == self.item_2)
        self.assertFalse(line_2.move_id)
        self.assertFalse(line_2.suggested)
        wizard.action_confirm()

        self.assertEqual(self.item_1.move_ids, receipt.move_ids)
        self.assertTrue(self.item_2.receipt_pending)
        self.declaration.expense_document_ids = self._broker_nfse()
        with self.assertRaisesRegex(UserError, "Pending items: 2"):
            self.declaration.action_create_landed_costs()

    def test_ambiguous_receipt_is_not_suggested(self):
        self._receive(self.product_1, 100.0, 53.0)
        self._receive(self.product_1, 100.0, 53.0)
        wizard = self._link_wizard()

        line_1 = wizard.line_ids.filtered(lambda line: line.item_id == self.item_1)
        self.assertFalse(line_1.move_id)
        with self.assertRaisesRegex(UserError, "at least one item"):
            wizard.action_confirm()

    def test_item_received_in_two_moves(self):
        first = self._receive(self.product_1, 60.0, 53.0)
        wizard = self._link_wizard()
        line_1 = wizard.line_ids.filtered(lambda line: line.item_id == self.item_1)
        # 60 of 100 units: not suggested, the user chooses it.
        self.assertFalse(line_1.move_id)
        line_1.move_id = first.move_ids
        wizard.action_confirm()
        self.assertAlmostEqual(self.item_1.received_qty, 60.0)
        self.assertTrue(self.item_1.receipt_pending)

        second = self._receive(self.product_1, 40.0, 53.0)
        wizard = self._link_wizard()
        line_1 = wizard.line_ids.filtered(lambda line: line.item_id == self.item_1)
        self.assertEqual(line_1.move_id, second.move_ids)
        wizard.action_confirm()
        self.assertFalse(self.item_1.receipt_pending)
        self.assertAlmostEqual(first.move_ids._get_duimp_customs_value(), 3180.0)
        self.assertAlmostEqual(second.move_ids._get_duimp_customs_value(), 2120.0)

    def test_move_linked_twice_or_to_another_product(self):
        receipt = self._receive(self.product_1, 100.0, 53.0)
        wizard = self._link_wizard()
        receipt.move_ids.duimp_item_id = self.item_1
        with self.assertRaisesRegex(UserError, "already linked"):
            wizard.action_confirm()
        with self.assertRaises(ValidationError):
            receipt.move_ids.duimp_item_id = self.item_2

    # ------------------------------------------------------------------
    # Landed costs from the DUIMP
    # ------------------------------------------------------------------

    def test_expense_is_not_allocated_twice(self):
        self._link_receipts()
        nfse = self._broker_nfse()
        self.declaration.expense_document_ids = nfse
        self.declaration.action_create_landed_costs()
        with self.assertRaisesRegex(UserError, "already has a landed cost"):
            self.declaration.action_create_landed_costs()
        with self.assertRaisesRegex(UserError, "already has a landed cost"):
            nfse.action_create_landed_cost()

    def test_receipts_must_be_done(self):
        for item in self.item_1 + self.item_2:
            self._receive(item.product_id, item.quantity, 50.0, validate=False)
        self._link_wizard().action_confirm()
        self.declaration.expense_document_ids = self._broker_nfse()
        with self.assertRaisesRegex(UserError, "Validate the receipts"):
            self.declaration.action_create_landed_costs()

    def test_zero_customs_value(self):
        self._link_receipts()
        self.declaration.item_ids.customs_value = 0.0
        self.declaration.expense_document_ids = self._freight_cte()
        with self.assertRaisesRegex(UserError, "no customs value"):
            self.declaration.action_create_landed_costs()

    def test_receipt_without_duimp_item_is_refused(self):
        picking = self._receive(self.product_1, 100.0, 53.0)
        document = self._freight_cte()
        document.landed_cost_picking_ids = picking
        document.landed_cost_split_method = "by_customs_value"
        with self.assertRaisesRegex(UserError, "linked to a DUIMP item"):
            document.action_create_landed_cost()

    def test_other_split_methods_are_kept(self):
        receipts = self._link_receipts()
        document = self._freight_cte()
        document.landed_cost_split_method = "by_quantity"
        self.declaration.expense_document_ids = document
        self.declaration.action_create_landed_costs()

        landed_cost = document.landed_cost_ids
        self.assertEqual(landed_cost.picking_ids, receipts[0] + receipts[1])
        adjustment_1 = landed_cost.valuation_adjustment_lines.filtered(
            lambda adj: adj.product_id == self.product_1
        )
        self.assertAlmostEqual(
            adjustment_1.additional_landed_cost,
            landed_cost.amount_total * 100.0 / 140.0,
            delta=0.01,
        )
        self.assertFalse(adjustment_1.customs_value)
