# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import Command
from odoo.tests import tagged

from odoo.addons.l10n_br_account.tests.common import AccountMoveBRCommon

from .tools import load_account_nfe_fixture_files


@tagged("post_install", "-at_install")
class TestNFeAutXML(AccountMoveBRCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))

        # Load demo data as fixtures if not already present
        if not cls.env.ref("product.product_product_10", raise_if_not_found=False):
            load_account_nfe_fixture_files(cls.env)

        cls.configure_normal_company_taxes()
        cls.accountant = cls.env["res.partner"].create(
            {"name": "Accountant", "is_company": True, "vat": "11.222.333/0001-81"}
        )
        cls.technical_support = cls.env["res.partner"].create(
            {"name": "Technical Support", "is_company": True}
        )

    def _authorize(self, accountant=False, technical_support=False):
        """Set up the company of the invoice and the one the user works on."""
        values = {}
        if accountant:
            values.update(
                accountant_id=self.accountant.id,
                nfe_authorize_accountant_download_xml=True,
            )
        if technical_support:
            values.update(
                technical_support_id=self.technical_support.id,
                nfe_authorize_technical_download_xml=True,
            )
        (self.env.company | self.company_data["company"]).write(values)

    def _create_invoice(self):
        """Create the invoice the way an integration (RPC, import) does.

        Not through the Form: the form view does not carry the autXML group.
        """
        operation = self.env.ref("l10n_br_fiscal.fo_venda")
        company = self.company_data["company"]
        return (
            self.env["account.move"]
            .with_company(company)
            .create(
                {
                    "move_type": "out_invoice",
                    "company_id": company.id,
                    "partner_id": self.partner_a.id,
                    "document_type_id": self.env.ref("l10n_br_fiscal.document_55").id,
                    "document_serie_id": self.empresa_lc_document_55_serie_1.id,
                    "fiscal_operation_id": operation.id,
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "product_id": self.product_b.id,
                                "quantity": 1,
                                "price_unit": 100.0,
                                "fiscal_operation_id": operation.id,
                                "fiscal_operation_line_id": self.env.ref(
                                    "l10n_br_fiscal.fo_venda_venda"
                                ).id,
                            }
                        )
                    ],
                }
            )
        )

    def test_invoice_authorizes_the_accountant(self):
        """An invoice of a company that authorizes the accountant can be created.

        The accountant is added to the autXML group of the NF-e. Before, the
        default of nfe40_autXML was also applied to the copy that account.move
        has of the field and the creation failed with: Invalid field
        'partner_id' on model 'nfe.40.autxml'.
        """
        self._authorize(accountant=True)
        invoice = self._create_invoice()
        autxml = invoice.fiscal_document_id.nfe40_autXML
        self.assertEqual(autxml.partner_id, self.accountant)
        self.assertEqual(autxml.nfe40_CNPJ, "11222333000181")

    def test_invoice_authorizes_accountant_and_technical_support(self):
        self._authorize(accountant=True, technical_support=True)
        invoice = self._create_invoice()
        self.assertEqual(
            invoice.fiscal_document_id.nfe40_autXML.partner_id,
            self.accountant | self.technical_support,
        )

    def test_invoice_without_authorization(self):
        """The company that did not ask for it has no autXML.

        The authorization is the one of the company of the invoice, not the
        one of the company the user is working on.
        """
        self.env.company.write(
            {
                "accountant_id": self.accountant.id,
                "nfe_authorize_accountant_download_xml": True,
            }
        )
        self.company_data["company"].nfe_authorize_accountant_download_xml = False
        invoice = self._create_invoice()
        self.assertFalse(invoice.fiscal_document_id.nfe40_autXML)
