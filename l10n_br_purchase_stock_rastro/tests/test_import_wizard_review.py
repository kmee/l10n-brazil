# Copyright 2026 KMEE
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
import os

from odoo import fields
from odoo.tests import TransactionCase, tagged

from odoo.addons import l10n_br_nfe


@tagged("post_install", "-at_install")
class TestImportWizardReview(TransactionCase):
    """The import wizard with the purchase and stock modules installed: what
    the import resolves by itself and what waits for a person."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        path = os.path.join(
            l10n_br_nfe.__path__[0],
            "tests",
            "nfe",
            "v4_00",
            "leiauteNFe",
            "NFe35200181583054000129550010000000052062777166.xml",
        )
        with open(path, "rb") as xml:
            cls.xml = xml.read()
        cls.company = cls.env.ref("base.main_company")
        cls.operation = cls.env.ref("l10n_br_fiscal.fo_compras")
        cls.supplier = cls.env["res.partner"].search(
            [("cnpj_cpf_stripped", "=", "81583054000129")], limit=1
        )
        if not cls.supplier:
            cls.supplier = cls.env["res.partner"].create(
                {"name": "XML Issuer Supplier", "cnpj_cpf": "81.583.054/0001-29"}
            )
        cls.product = cls.env["product.product"].search(
            [("default_code", "=", "E-COM11")], limit=1
        )
        if not cls.product:
            cls.product = cls.env["product.product"].create(
                {
                    "name": "Cabinet with Doors",
                    "default_code": "E-COM11",
                    "purchase_ok": True,
                    "type": "product",
                }
            )
        cls.env["product.supplierinfo"].search(
            [("partner_id", "=", cls.supplier.id), ("product_code", "=", "E-COM11")]
        ).unlink()
        cls.order = cls._confirmed_order()

    @classmethod
    def _confirmed_order(cls):
        order = cls.env["purchase.order"].create(
            {
                "partner_id": cls.supplier.id,
                "company_id": cls.company.id,
                "fiscal_operation_id": cls.company.purchase_fiscal_operation_id.id
                or cls.operation.id,
            }
        )
        cls.env["purchase.order.line"].create(
            {
                "order_id": order.id,
                "product_id": cls.product.id,
                "name": cls.product.name,
                "product_qty": 2.0,
                "price_unit": 10.0,
                "date_planned": fields.Datetime.now(),
            }
        )
        order.button_confirm()
        return order

    def _wizard(self, xml=None):
        wizard = self.env["l10n_br_fiscal.document.import.wizard"].create(
            {
                "company_id": self.company.id,
                "file": base64.b64encode(xml or self.xml),
            }
        )
        wizard._onchange_file()
        wizard.fiscal_operation_id = self.operation
        return wizard

    def _declared_xml(self):
        return (
            self.xml.decode()
            .replace(
                "</prod>",
                f"<xPed>{self.order.name}</xPed><nItemPed>1</nItemPed></prod>",
                1,
            )
            .encode()
        )

    def test_the_order_declared_by_the_supplier_resolves_product_and_origin(self):
        wizard = self._wizard(self._declared_xml())
        line = wizard.imported_products_ids
        self.assertEqual(line.product_source, "order")
        self.assertTrue(line.match_source_trusted)
        wizard._import_edoc()
        fiscal_line = wizard.document_id.fiscal_line_ids
        self.assertEqual(fiscal_line.import_state, "resolved")
        self.assertEqual(fiscal_line.import_purchase_line_id, self.order.order_line)
        self.assertEqual(fiscal_line.import_origin_state, "resolved")

    def test_an_origin_only_preselected_is_a_suggestion(self):
        """Without the reference of the file, the only open line of the supplier
        for the product is preselected, but nobody decided it."""
        wizard = self._wizard()
        line = wizard.imported_products_ids
        self.assertTrue(line.match_source_id)
        self.assertFalse(line.match_source_trusted)
        wizard._import_edoc()
        fiscal_line = wizard.document_id.fiscal_line_ids
        self.assertEqual(fiscal_line.import_purchase_line_id, self.order.order_line)
        self.assertEqual(fiscal_line.import_origin_state, "suggested")
        self.assertEqual(fiscal_line.import_state, "matched")

    def test_the_origin_chosen_in_the_grid_is_a_decision(self):
        wizard = self._wizard()
        line = wizard.imported_products_ids
        source = line.match_source_id
        line.match_source_id = False
        line.match_source_id = source
        self.assertTrue(line.match_source_trusted)
        wizard._import_edoc()
        fiscal_line = wizard.document_id.fiscal_line_ids
        self.assertEqual(fiscal_line.import_origin_state, "resolved")
