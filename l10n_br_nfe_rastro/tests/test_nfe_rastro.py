# Copyright 2024 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import datetime

from odoo.exceptions import UserError

from .common import NFE_NS, NFeRastroCommon


class TestNFeRastro(NFeRastroCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        d = cls._date
        cls.lot_a = cls._create_lot(
            "LOT-A", cls._datetime(d(2026, 1, 10)), cls._datetime(d(2027, 1, 10))
        )
        # 01:00 UTC on March 1st is still February 28th in Brazil (UTC-3)
        cls.lot_b = cls._create_lot(
            "LOT-B", cls._datetime(d(2026, 2, 5)), datetime(2027, 3, 1, 1, 0)
        )
        cls._add_stock(cls.lot_a, 10)
        cls._add_stock(cls.lot_b, 10)

    def test_invoice_from_picking_fills_rastro(self):
        """Each lot shipped becomes one traceability group with its own
        quantity and the lot dates as seen in Brazil."""
        picking = self._ship(self.product, {self.lot_a: 2, self.lot_b: 3})
        invoice = self._invoice(picking)
        line = invoice.invoice_line_ids.filtered(
            lambda ln: ln.product_id == self.product
        )
        self.assertEqual(line.quantity, 5)
        d = self._date
        self.assertEqual(
            self._rastro_data(line),
            [
                ("LOT-A", 2.0, d(2026, 1, 10), d(2027, 1, 10)),
                ("LOT-B", 3.0, d(2026, 2, 5), d(2027, 2, 28)),
            ],
        )

    def test_invoice_without_lots_has_no_rastro(self):
        product = self.env.ref("product.product_product_12")
        self.env["stock.quant"].with_company(self.company)._update_available_quantity(
            product, self.stock_location, 5
        )
        picking = self._ship(product, {self.env["stock.lot"]: 2})
        invoice = self._invoice(picking)
        self.assertFalse(invoice.invoice_line_ids.nfe40_rastro)

    def test_nfe_xml_has_rastro_and_is_valid(self):
        """Posting the invoice confirms the NF-e: the XML carries one
        <rastro> per lot and passes the schema validation."""
        picking = self._ship(self.product, {self.lot_a: 2, self.lot_b: 3})
        invoice = self._invoice(picking)
        invoice.action_post()
        document = invoice.fiscal_document_id
        self.assertEqual(document.state_edoc, "a_enviar")
        self.assertFalse(document.xml_error_message)
        prods = self._xml_det_prod(document)
        prod = next(
            p for p in prods if p.findtext("nfe:cProd", namespaces=NFE_NS) == "TRACED-1"
        )
        rastros = [
            tuple(
                r.findtext(f"nfe:{tag}", namespaces=NFE_NS)
                for tag in ("nLote", "qLote", "dFab", "dVal")
            )
            for r in prod.findall("nfe:rastro", NFE_NS)
        ]
        self.assertEqual(
            sorted(rastros),
            [
                ("LOT-A", "2.000", "2026-01-10", "2027-01-10"),
                ("LOT-B", "3.000", "2026-02-05", "2027-02-28"),
            ],
        )

    def test_missing_manufacturing_date_blocks_confirmation(self):
        lot = self._create_lot(
            "LOT-NO-DFAB", False, self._datetime(self._date(2027, 5, 1))
        )
        self._add_stock(lot, 5)
        picking = self._ship(self.product, {lot: 1})
        invoice = self._invoice(picking)
        with self.assertRaisesRegex(
            UserError, "LOT-NO-DFAB: manufacturing date missing"
        ):
            invoice.action_post()

    def test_expiration_before_manufacturing_blocks_confirmation(self):
        """Rule I84-10 (rejection 870)."""
        d = self._date
        lot = self._create_lot(
            "LOT-BAD-DVAL", self._datetime(d(2026, 3, 1)), self._datetime(d(2026, 2, 1))
        )
        self._add_stock(lot, 5)
        picking = self._ship(self.product, {lot: 1})
        invoice = self._invoice(picking)
        with self.assertRaisesRegex(
            UserError, "expiration date is before the manufacturing date"
        ):
            invoice.action_post()

    def test_manufacturing_after_issue_blocks_confirmation(self):
        """Rule I83-10 (rejection 877)."""
        d = self._date
        lot = self._create_lot(
            "LOT-FUTURE", self._datetime(d(2099, 1, 1)), self._datetime(d(2099, 6, 1))
        )
        self._add_stock(lot, 5)
        picking = self._ship(self.product, {lot: 1})
        invoice = self._invoice(picking)
        with self.assertRaisesRegex(
            UserError, "manufacturing date is after the issue date"
        ):
            invoice.action_post()

    def test_fill_as_fiscal_user(self):
        """A fiscal user, not an NF-e manager, can rebuild the groups."""
        picking = self._ship(self.product, {self.lot_a: 1})
        invoice = self._invoice(picking)
        user = self.env["res.users"].create(
            {
                "name": "Fiscal User",
                "login": "rastro_fiscal_user",
                "company_id": self.company.id,
                "company_ids": [(6, 0, self.company.ids)],
                "groups_id": [
                    (
                        6,
                        0,
                        (
                            self.env.ref("account.group_account_invoice")
                            | self.env.ref("stock.group_stock_user")
                            | self.env.ref("l10n_br_fiscal.group_user")
                        ).ids,
                    )
                ],
            }
        )
        line = invoice.invoice_line_ids.filtered(
            lambda ln: ln.product_id == self.product
        )
        line.fiscal_document_line_id.nfe40_rastro.unlink()
        line.with_user(user).with_company(self.company)._fill_nfe40_rastro()
        self.assertEqual(line.nfe40_rastro.mapped("nfe40_nLote"), ["LOT-A"])
