# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import re
from unittest import SkipTest

from odoo import Command, fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools import file_open

FIXTURE = (
    "l10n_br_nfe/tests/nfe/v4_00/leiauteNFe/"
    "NFe35200181583054000129550010000000052062777166.xml"
)
FIXTURE_DEST = re.compile(rb"(<dest>\s*)<(?:CNPJ|CPF)>\d+</(?:CNPJ|CPF)>")


@tagged("post_install", "-at_install")
class TestOldWizardOrigin(TransactionCase):
    """The "Import NF-e XML" window of the former assistant gives the origin of
    the goods to the document like the new assistant does: a line of a product
    that the supplier has an open order for is not billed before someone decides
    where it comes from."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # the former assistant is a window of the NF-e module, which the links
        # of the purchases do not depend on
        if "l10n_br_nfe.import_xml.products" not in cls.env:
            raise SkipTest("The NF-e module is not installed")
        cls.company = cls.env.ref("l10n_br_base.empresa_simples_nacional")
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                allowed_company_ids=[cls.company.id],
            )
        )
        cls.supplier = cls.env.ref("l10n_br_base.lucro_presumido_partner")
        cls.operation = cls.env.ref("l10n_br_fiscal.fo_compras")
        cls.product = cls.env["product.product"].create(
            {"name": "Imported product", "type": "consu"}
        )

    def _order(self):
        order = (
            self.env["purchase.order"]
            .with_company(self.company)
            .create(
                {
                    "partner_id": self.supplier.id,
                    "company_id": self.company.id,
                    "order_line": [
                        Command.create(
                            {
                                "product_id": self.product.id,
                                "name": self.product.name,
                                "product_qty": 10.0,
                                "product_uom": self.product.uom_id.id,
                                "price_unit": 14.0,
                                "date_planned": fields.Datetime.now(),
                            }
                        )
                    ],
                }
            )
        )
        order.button_confirm()
        return order

    def _import(self):
        with file_open(FIXTURE, "rb") as xml_file:
            content = xml_file.read()
        recipient = self.company.partner_id.cnpj_cpf_stripped
        content = FIXTURE_DEST.sub(rb"\1<CNPJ>%s</CNPJ>" % recipient.encode(), content)
        wizard = (
            self.env["l10n_br_fiscal.document.import.wizard"]
            .with_company(self.company)
            .create(
                {
                    "company_id": self.company.id,
                    "file": base64.b64encode(content),
                }
            )
        )
        wizard._onchange_file()
        wizard.fiscal_operation_id = self.operation
        wizard.imported_products_ids.write(
            {"product_id": self.product.id, "uom_internal": self.product.uom_id.id}
        )
        wizard.action_import_and_open_document()
        return wizard.document_id

    def test_the_line_with_an_open_order_has_its_origin_suggested(self):
        order = self._order()

        document = self._import()

        line = document.fiscal_line_ids
        self.assertEqual(len(line), 1)
        self.assertEqual(line.product_id, self.product)
        self.assertEqual(line.import_origin_state, "suggested")
        self.assertEqual(line.import_purchase_line_id, order.order_line)

    def test_the_bill_is_refused_until_the_origin_is_decided(self):
        self._order()
        document = self._import()

        with self.assertRaisesRegex(UserError, "not decided yet"):
            document.action_generate_invoice()

        document.action_confirm_import_origins()
        self.assertEqual(document.fiscal_line_ids.import_origin_state, "resolved")
        document.action_generate_invoice()
        self.assertTrue(document.move_ids)

    def test_the_line_without_an_order_has_no_origin_state(self):
        document = self._import()

        self.assertFalse(document.fiscal_line_ids.import_origin_state)
