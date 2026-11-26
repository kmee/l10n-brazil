# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import os
import re

from odoo.tests import TransactionCase, tagged

from odoo.addons import l10n_br_account_nfe

FIXTURE = os.path.join(
    l10n_br_account_nfe.__path__[0],
    "tests",
    "nfe",
    "35231149647316000169550010000661061151600085-nfe.xml",
)
FIXTURE_DEST = re.compile(rb"(<dest>\s*)<(?:CNPJ|CPF)>\d+</(?:CNPJ|CPF)>")


@tagged("post_install", "-at_install")
class TestOldWizardImport(TransactionCase):
    """The "Import NF-e XML" window of the former assistant is itself the review:
    the document it creates goes to the invoice with no other step."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=True,
                allowed_company_ids=[cls.company.id],
            )
        )
        cls.operation = cls.env.ref("l10n_br_fiscal.fo_compras")

    def _wizard(self):
        with open(FIXTURE, "rb") as xml_file:
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
                    "allow_product_creation": True,
                }
            )
        )
        wizard._onchange_file()
        wizard.fiscal_operation_id = self.operation
        return wizard

    def test_the_imported_document_goes_to_the_invoice(self):
        wizard = self._wizard()

        wizard.action_import_and_open_document()
        document = wizard.document_id

        self.assertTrue(document.fiscal_line_ids)
        self.assertEqual(
            set(document.fiscal_line_ids.mapped("import_state")), {"resolved"}
        )
        self.assertEqual(document.import_state, "resolved")
        self.assertTrue(document.edi_can_generate_invoice)
        action = document.action_generate_invoice()
        self.assertEqual(action["res_model"], "account.move")
        self.assertTrue(document.move_ids)

    def test_the_import_of_the_invoice_still_creates_the_bill(self):
        wizard = self._wizard()

        action = wizard.action_import_and_open_move()

        self.assertEqual(action["res_model"], "account.move")
        move = self.env["account.move"].browse(action["res_id"])
        self.assertTrue(move.fiscal_document_id.imported_document)
