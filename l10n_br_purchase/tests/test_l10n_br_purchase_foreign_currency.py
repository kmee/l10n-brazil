# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo.tests import tagged

from .test_l10n_br_purchase import L10nBrPurchaseBaseTest


@tagged("post_install", "-at_install")
class TestL10nBrPurchaseForeignCurrency(L10nBrPurchaseBaseTest):
    """PO total in foreign currency with import operation must be what
    is owed to the supplier, without import taxes (paid via DI in BRL)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.company_ids += cls.company
        cls.env.user.company_id = cls.company
        cls.eur = cls.env.ref("base.EUR")
        cls.eur.active = True
        cls.usd = cls.env.ref("base.USD")
        cls.usd.active = True
        for cur, rate in ((cls.eur, 1 / 6.30), (cls.usd, 1 / 5.40)):
            cls.env["res.currency.rate"].create(
                {
                    "currency_id": cur.id,
                    "company_id": cls.company.id,
                    "name": "2026-01-01",
                    "rate": rate,
                }
            )
        cls.cfop_3102 = cls.env.ref("l10n_br_fiscal.cfop_3102")
        cls.cfop_3556 = cls.env.ref("l10n_br_fiscal.cfop_3556")
        cls.cfop_1102 = cls.env.ref("l10n_br_fiscal.cfop_1102")

    def _prepare_po(self, currency, cfop, lines=1, extra=None):
        po = self.po_products
        if po.state != "draft":
            po.button_cancel()
            po.button_draft()
        po.company_id.delivery_costs = "line"
        po.currency_id = currency
        self._run_purchase_order_onchanges(po)
        order_lines = po.order_line[:lines]
        (po.order_line - order_lines).unlink()
        for line in order_lines:
            self._run_purchase_line_onchanges(line)
            line.write(
                dict(
                    {
                        "product_qty": 10.0,
                        "price_unit": 100.0,
                        "discount": 0.0,
                        "freight_value": 0.0,
                        "insurance_value": 0.0,
                        "other_value": 0.0,
                        "cfop_id": cfop.id,
                    },
                    **(extra or {}),
                )
            )
        return po

    def test_a_foreign_import_total_without_taxes(self):
        for cfop in (self.cfop_3102, self.cfop_3556):
            po = self._prepare_po(self.eur, cfop)
            line = po.order_line[0]
            self.assertTrue(line._is_foreign_import())
            self.assertEqual(po.amount_untaxed, 1000.0)
            self.assertEqual(po.amount_tax, 0.0)
            self.assertEqual(po.amount_total, 1000.0)
            self.assertEqual(line.price_subtotal, 1000.0)
            self.assertEqual(line.price_tax, 0.0)
            self.assertEqual(line.price_total, 1000.0)

    def test_a2_freight_insurance(self):
        po = self._prepare_po(
            self.eur,
            self.cfop_3102,
            extra={"freight_value": 50.0, "insurance_value": 10.0},
        )
        self.assertEqual(po.amount_total, 1060.0)
        self.assertEqual(po.amount_tax, 0.0)

    def test_a3_many_lines(self):
        po = self._prepare_po(self.eur, self.cfop_3102, lines=2)
        n = len(po.order_line)
        self.assertEqual(po.amount_total, 1000.0 * n)
        self.assertEqual(po.amount_tax, 0.0)

    def test_b_brl_unchanged(self):
        """BRL PO keeps the current behavior, with or without CFOP 3xxx."""
        for cfop in (self.cfop_1102, self.cfop_3102):
            po = self._prepare_po(self.company.currency_id, cfop)
            line = po.order_line[0]
            self.assertFalse(line._is_foreign_import())
            self.assertEqual(po.amount_untaxed, line.fiscal_amount_untaxed)
            self.assertEqual(po.amount_tax, line.fiscal_amount_tax)
            self.assertEqual(po.amount_total, line.fiscal_amount_total)

    def test_b3_usd_domestic_operation(self):
        po = self._prepare_po(self.usd, self.cfop_1102)
        line = po.order_line[0]
        self.assertFalse(line._is_foreign_import())
        self.assertEqual(po.amount_total, line.fiscal_amount_total)

    def test_c_invoice_from_foreign_import_po(self):
        """Vendor bill from a foreign import PO owes exactly the PO total."""
        po = self._prepare_po(self.eur, self.cfop_3102)
        po.order_line.product_id.purchase_method = "purchase"
        po.with_context(tracking_disable=True).button_confirm()
        po.action_create_invoice()
        invoice = po.invoice_ids[:1]
        self.assertTrue(invoice)
        self.assertEqual(invoice.currency_id, self.eur)
        self.assertEqual(invoice.amount_total, po.amount_total)
        self.assertEqual(invoice.amount_tax, 0.0)
        self.assertEqual(invoice.amount_residual, po.amount_total)

    def test_c2_domestic_invoice_keeps_fiscal_data(self):
        po = self._prepare_po(self.company.currency_id, self.cfop_3102)
        po.order_line.product_id.purchase_method = "purchase"
        po.with_context(tracking_disable=True).button_confirm()
        po.action_create_invoice()
        invoice = po.invoice_ids[:1]
        self.assertEqual(invoice.fiscal_operation_id, po.fiscal_operation_id)

    def test_d_currency_switch_recomputes(self):
        po = self._prepare_po(self.company.currency_id, self.cfop_3102)
        brl_total = po.amount_total
        self.assertGreater(po.amount_tax, 0.0)
        po.currency_id = self.eur
        self.assertEqual(po.amount_total, 1000.0)
        self.assertEqual(po.amount_tax, 0.0)
        po.currency_id = self.company.currency_id
        self.assertEqual(po.amount_total, brl_total)

    def test_e_informative_icms_and_price_unit(self):
        po = self._prepare_po(self.eur, self.cfop_3102)
        line = po.order_line[0]
        self.assertEqual(line.price_unit, 100.0)
        self.assertGreater(line.icms_value, 0.0)
        self.assertEqual(po.amount_total, 1000.0)

    def test_f_mixed_po(self):
        po = self._prepare_po(self.eur, self.cfop_3102, lines=2)
        domestic = po.order_line[1]
        domestic.cfop_id = self.cfop_1102
        self.assertFalse(domestic._is_foreign_import())
        self.assertTrue(po.order_line[0]._is_foreign_import())
        self.assertEqual(
            po.amount_total,
            1000.0 + domestic.fiscal_amount_total,
        )

    def test_g_tax_totals(self):
        po = self._prepare_po(self.eur, self.cfop_3102)
        self.assertEqual(po.tax_totals["total_amount_currency"], 1000.0)

    def test_h_add_fields_without_record(self):
        line_model = self.env["purchase.order.line"]
        self.assertIn("freight_value", line_model._add_fields_to_amount())
        self.assertNotIn("icms_value", line_model._add_fields_to_amount())

    def test_i_rounding_four_decimals(self):
        po = self._prepare_po(
            self.eur, self.cfop_3102, extra={"product_qty": 10.0, "price_unit": 99.9999}
        )
        self.assertEqual(po.amount_total, self.eur.round(999.999))
        self.assertEqual(po.amount_tax, 0.0)
