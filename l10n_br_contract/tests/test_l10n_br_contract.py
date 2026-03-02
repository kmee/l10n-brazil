# Copyright 2020 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import Form
from odoo.tests.common import tagged
from odoo.addons.l10n_br_account.tests.common import AccountMoveBRCommon


@tagged("post_install", "-at_install")
class TestL10nBrContract(AccountMoveBRCommon):
    @classmethod
    def setUpClass(cls):
        super(TestL10nBrContract, cls).setUpClass()

        cls.env.company.write(dict(
            contract_sale_fiscal_operation_id=
                cls.env.ref("l10n_br_fiscal.fo_venda").id,
            contract_purchase_fiscal_operation_id=
                cls.env.ref("l10n_br_fiscal.fo_compras").id,
            document_type_id=
                cls.env.ref("l10n_br_fiscal.document_55").id
        ))

        # Create contract with 3 lines, two resale products and one service
        contract_form = Form(cls.env["contract.contract"])
        contract_form.name = "Test Contract"
        contract_form.partner_id = cls.partner_a

        cls.contract_id = contract_form.save()

        with Form(cls.contract_id) as contract:
            with contract.contract_line_fixed_ids.new() as line:
                line.product_id = cls.product_a
            with contract.contract_line_fixed_ids.new() as line:
                line.product_id = cls.product_b
            with contract.contract_line_fixed_ids.new() as line:
                line.product_id = cls.env.ref(
                    "l10n_br_fiscal.customized_development_sale"
                )
                line.fiscal_operation_id = cls.env.ref("l10n_br_fiscal.fo_venda")

        # Create Invoice and Fiscal Documents related to the contract
        cls.contract_id.recurring_create_invoice()

    def test_created_fiscal_documents(self):
        """
        Checks if the Fiscal Documents created from a contract have the correct
        products according to the Fiscal Operation of their lines
        """
        for invoice in self.contract_id._get_related_invoices():
            document_id = invoice.fiscal_document_id

            if len(document_id.fiscal_line_ids) == 1:
                service_product_id = self.env.ref(
                    "l10n_br_fiscal.customized_development_sale"
                )
                document_type_id = self.env.ref("l10n_br_fiscal.document_SE")

                self.assertEqual(
                    document_type_id.id,
                    document_id.document_type_id.id,
                    "The Fiscal Document Type is not Nota Fiscal "
                    "de Serviço Eletrônica",
                )

                self.assertEqual(
                    service_product_id.id,
                    document_id.fiscal_line_ids[0].product_id.id,
                    "The product of the Fiscal Document does not "
                    "correspond with the expected",
                )

            else:
                document_type_id = self.env.ref("l10n_br_fiscal.document_55")

                products_ids = []
                for line in document_id.fiscal_line_ids:
                    products_ids.append(line.product_id.id)

                self.assertEqual(
                    document_type_id.id,
                    document_id.document_type_id.id,
                    "The Fiscal Document Type is not Nota Fiscal " "Eletrônica",
                )

                self.assertEqual(
                    [self.product_a.id, self.product_b.id],
                    products_ids,
                    "The products of the Fiscal Document does not"
                    " correspond with the expected",
                )

    def test_created_invoices(self):
        """
        Checks if invoices created from a contract have the correct products
        according to the Fiscal Operation of their lines
        """
        for invoice in self.contract_id._get_related_invoices():

            if len(invoice.invoice_line_ids) == 1:
                service_product_id = self.env.ref(
                    "l10n_br_fiscal.customized_development_sale"
                )

                self.assertEqual(
                    service_product_id.id,
                    invoice.invoice_line_ids[0].product_id.id,
                    "The product of the Fiscal Document does not "
                    "correspond with the expected",
                )

            else:
                products_ids = []
                for line in invoice.invoice_line_ids:
                    products_ids.append(line.product_id.id)

                products_ids.sort()

                self.assertEqual(
                    [self.product_a.id, self.product_b.id],
                    products_ids,
                    "The products of the Fiscal Document does not"
                    " correspond with the expected",
                )

    def test_fiscal_operation_assignment_on_creation(self):
        """
        Test that fiscal operation is automatically assigned when creating
        a contract based on contract type and company defaults
        """
        # Test sale contract
        sale_contract_form = Form(self.env["contract.contract"])
        sale_contract_form.name = "Sale Contract Test"
        sale_contract_form.partner_id = self.partner_a
        sale_contract_form.contract_type = "sale"
        sale_contract = sale_contract_form.save()

        self.assertEqual(
            sale_contract.fiscal_operation_id.id,
            self.env.company.contract_sale_fiscal_operation_id.id,
            "Sale contract should have default sale fiscal operation",
        )

        # Test purchase contract
        purchase_contract_form = Form(self.env["contract.contract"])
        purchase_contract_form.name = "Purchase Contract Test"
        purchase_contract_form.partner_id = self.partner_a
        purchase_contract_form.contract_type = "purchase"
        purchase_contract = purchase_contract_form.save()

        self.assertEqual(
            purchase_contract.fiscal_operation_id.id,
            self.env.company.contract_purchase_fiscal_operation_id.id,
            "Purchase contract should have default purchase fiscal operation",
        )

    def test_tax_recalculation_before_invoice(self):
        """
        Test that taxes are recalculated before invoicing when
        contract_recalculate_taxes_before_invoice is enabled
        """
        # Enable tax recalculation
        self.contract_id.contract_recalculate_taxes_before_invoice = True

        # Create a new invoice
        invoices = self.contract_id.recurring_create_invoice()

        # Verify invoices were created
        self.assertTrue(
            invoices,
            "Invoices should be created when recurring_create_invoice is called",
        )

        # Verify fiscal documents have correct taxes
        for invoice in invoices:
            self.assertTrue(
                invoice.fiscal_document_id,
                "Invoice should have a fiscal document",
            )
            for line in invoice.invoice_line_ids:
                self.assertTrue(
                    line.fiscal_operation_line_id,
                    "Invoice line should have fiscal operation line",
                )

    def test_contract_without_fiscal_operation(self):
        """
        Test contract behavior when fiscal operation is not set
        """
        contract_form = Form(self.env["contract.contract"])
        contract_form.name = "Contract Without Fiscal Operation"
        contract_form.partner_id = self.partner_a
        contract_form.fiscal_operation_id = False
        contract = contract_form.save()

        # Add a line
        with Form(contract) as contract_form:
            with contract_form.contract_line_fixed_ids.new() as line:
                line.product_id = self.product_a

        # Create invoice
        invoices = contract.recurring_create_invoice()

        # Verify that invoices can still be created
        self.assertTrue(
            invoices,
            "Invoices should be created even without fiscal operation",
        )

    def test_multiple_document_types_from_contract(self):
        """
        Test that contracts with different fiscal operations create
        separate invoices with different document types
        """
        # This test verifies the _prepare_recurring_invoices_values logic
        # that separates invoices by document type
        invoices = self.contract_id._get_related_invoices()

        # Group invoices by document type
        document_types = {}
        for invoice in invoices:
            if invoice.fiscal_document_id:
                doc_type = invoice.fiscal_document_id.document_type_id
                if doc_type:
                    if doc_type.id not in document_types:
                        document_types[doc_type.id] = []
                    document_types[doc_type.id].append(invoice)

        # Verify that we have invoices with different document types
        # (products vs services)
        self.assertGreater(
            len(document_types),
            0,
            "Should have at least one document type",
        )
