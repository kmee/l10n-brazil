# Copyright (C) 2026  Luis Felipe Mileo - KMEE
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo.tests import TransactionCase


class TestDocumentImportLine(TransactionCase):
    """Review states and persisted de-para on imported document lines."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.uom_unit = cls.env.ref("uom.product_uom_unit")
        cls.uom_kg = cls.env.ref("uom.product_uom_kgm")
        cls.uom_ton = cls.env.ref("uom.product_uom_ton")
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Fornecedor Farinha",
                "state_id": cls.env.ref("base.state_br_mg").id,
                "country_id": cls.env.ref("base.br").id,
            }
        )
        cls.product = cls.env["product.product"].create(
            {
                "name": "Farinha de Trigo Tipo 1",
                "uom_id": cls.uom_kg.id,
                "uom_po_id": cls.uom_kg.id,
            }
        )
        cls.company = cls.env.company
        cls.company.state_id = cls.env.ref("base.state_br_sp")
        cls.company.country_id = cls.env.ref("base.br")
        cls.document = cls.env["l10n_br_fiscal.document"].create(
            {
                "document_type_id": cls.env.ref(
                    "l10n_br_fiscal.document_55_serie_1"
                ).id,
                # fiscal_operation_type is a stored related of the operation
                "fiscal_operation_id": cls.env.ref("l10n_br_fiscal.fo_compras").id,
                "imported_document": True,
                "partner_id": cls.partner.id,
                "company_id": cls.company.id,
            }
        )
        # A line faithfully imported: supplier sells bags (SC) of 25kg.
        cls.line = cls.env["l10n_br_fiscal.document.line"].create(
            {
                "document_id": cls.document.id,
                "name": "FARINHA TRIGO T1 SC 25KG",
                "quantity": 2.0,
                "price_unit": 100.0,
                "uom_id": cls.uom_unit.id,
                "partner_cfop_id": cls.env.ref("l10n_br_fiscal.cfop_6102").id,
            }
        )

    def test_init_and_aggregate_states(self):
        line_matched = self.env["l10n_br_fiscal.document.line"].create(
            {
                "document_id": self.document.id,
                "name": "Linha ja casada",
                "product_id": self.product.id,
                "quantity": 1.0,
                "price_unit": 10.0,
                "uom_id": self.uom_kg.id,
            }
        )
        self.document._init_import_states()
        self.assertEqual(self.line.import_state, "pending")
        self.assertEqual(line_matched.import_state, "matched")
        self.assertEqual(self.document.import_state, "pending")
        self.assertEqual(self.document.import_pending_count, 2)

        line_matched.product_id = self.product
        line_matched._apply_import_depara()
        self.assertEqual(self.document.import_state, "in_progress")

        self.line.product_id = self.product
        self.line._apply_import_depara()
        self.assertEqual(self.document.import_state, "resolved")
        self.assertEqual(self.document.import_pending_count, 0)

    def test_apply_depara_math_and_snapshot(self):
        """Quantity times factor, price divided by it: the total is
        invariant, and the supplier values are preserved as a snapshot."""
        self.line._apply_import_depara(
            product=self.product, uom=self.uom_kg, factor=25.0
        )
        self.assertEqual(self.line.import_state, "resolved")
        # snapshot of the supplier nomenclature
        self.assertEqual(self.line.partner_quantity, 2.0)
        self.assertEqual(self.line.partner_price_unit, 100.0)
        self.assertTrue(self.line.partner_uom_code)
        # converted to the internal unit, total preserved
        self.assertEqual(self.line.uom_id, self.uom_kg)
        self.assertEqual(self.line.quantity, 50.0)
        self.assertEqual(self.line.price_unit, 4.0)
        self.assertAlmostEqual(
            self.line.quantity * self.line.price_unit,
            self.line.partner_quantity * self.line.partner_price_unit,
            places=2,
        )
        # the de-para learning is persisted on the supplier info
        self.assertTrue(self.line.import_supplierinfo_id)
        self.assertEqual(self.line.import_supplierinfo_id.partner_id, self.partner)
        self.assertIn(
            self.line.import_supplierinfo_id,
            self.product.product_tmpl_id.seller_ids,
        )

    def test_apply_depara_is_idempotent_on_snapshot(self):
        """Re-applying the de-para (e.g. fixing a wrong factor) must convert
        from the original supplier snapshot, not compound the conversion."""
        self.line._apply_import_depara(
            product=self.product, uom=self.uom_kg, factor=25.0
        )
        self.line._apply_import_depara(uom=self.uom_ton, factor=0.025)
        self.assertEqual(self.line.partner_quantity, 2.0)
        self.assertAlmostEqual(self.line.quantity, 0.05, places=4)
        self.assertAlmostEqual(self.line.price_unit, 4000.0, places=2)

    def test_recompute_guards_preserve_imported_values(self):
        """Setting the internal product on an imported line must not let the
        stored computes overwrite the values imported from the file."""
        self.line.product_id = self.product
        self.assertEqual(self.line.name, "FARINHA TRIGO T1 SC 25KG")
        self.assertEqual(self.line.quantity, 2.0)
        self.assertEqual(self.line.price_unit, 100.0)
        self.assertEqual(self.line.uom_id, self.uom_unit)

    def test_suggest_fiscal_operation_in_via_inverse_cfop(self):
        """The inbound operation is suggested through the inverse CFOP of
        the CFOP declared by the counterparty."""
        cfop_6102 = self.env.ref("l10n_br_fiscal.cfop_6102")
        cfop_2102 = self.env.ref("l10n_br_fiscal.cfop_2102")
        cfop_6102.cfop_inverse_id = cfop_2102
        operation = self.env["l10n_br_fiscal.operation"].create(
            {
                "code": "TST-COMPRA",
                "name": "Compra para revenda (teste)",
                "fiscal_operation_type": "in",
                "fiscal_type": "purchase",
                "state": "approved",
            }
        )
        self.env["l10n_br_fiscal.operation.line"].create(
            {
                "fiscal_operation_id": operation.id,
                "name": "Compra para revenda (teste)",
                "cfop_internal_id": self.env.ref("l10n_br_fiscal.cfop_1102").id,
                "cfop_external_id": cfop_2102.id,
                "state": "approved",
            }
        )
        # Several approved operations may reference the inverse CFOP (the
        # core demo data already wires fo_compras to it): the suggestion is
        # the first approved candidate, and it must be an inbound operation
        # whose lines reference the inverse CFOP.
        suggested = self.line._suggest_fiscal_operation_in()
        self.assertTrue(suggested)
        self.assertEqual(suggested.fiscal_operation_type, "in")
        self.assertIn(
            cfop_2102,
            suggested.line_ids.cfop_internal_id
            | suggested.line_ids.cfop_external_id
            | suggested.line_ids.cfop_export_id,
        )
        self.assertEqual(self.document._suggest_fiscal_operation(), suggested)

        # the wizard lookup goes through the same inverse path now
        wizard = self.env["l10n_br_fiscal.document.import.wizard"].create({})
        self.assertEqual(
            wizard._find_fiscal_operation("6102", "Compra para revenda (teste)", "in"),
            operation,
        )

    def test_cfop_warning_on_line(self):
        """The declared CFOP is checked against the real geography."""
        # issuer MG x company SP with an intrastate CFOP -> warn
        self.line.partner_cfop_id = self.env.ref("l10n_br_fiscal.cfop_5102")
        self.assertTrue(self.line._get_cfop_warning())
        # interstate CFOP -> consistent
        self.line.partner_cfop_id = self.env.ref("l10n_br_fiscal.cfop_6102")
        self.assertFalse(self.line._get_cfop_warning())
        # foreign trade CFOP with both parties in Brazil -> warn
        self.line.partner_cfop_id = self.env.ref("l10n_br_fiscal.cfop_3102")
        self.assertTrue(self.line._get_cfop_warning())
        # foreign issuer with a foreign trade CFOP -> consistent
        self.partner.country_id = self.env.ref("base.us")
        self.partner.state_id = False
        self.assertFalse(self.line._get_cfop_warning())
