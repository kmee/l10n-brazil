# @ 2021 KMEE - www.kmee.com.br
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from odoo.tests.common import TransactionCase


class TestTaxCalc(TransactionCase):
    def setUp(self):
        super(TestTaxCalc, self).setUp()

        self.fiscal_document_demo_1 = self.env.ref("l10n_br_fiscal.demo_nfe_same_state")
        self.fiscal_document_demo_2 = self.env.ref(
            "l10n_br_fiscal.demo_nfe_sales_return_same_state"
        )

    def test_tax_engine_automatic(self):
        """
        In the test cases that have been added, it's only checked that the tax values
            were loaded correctly based on the 'tax_calc' selected for that operation
            and the module's demo data.

        Standard behavior of the system, where as soon as a product is selected,
            all taxes referring to it are already loaded - usually linked to the
            NCM.
        """
        product = self.fiscal_document_demo_1.line_ids[0]

        self.assertEqual(
            product.icms_percent,
            12.0,
            "The ICMS percent does not match the standard in product from Automatic "
            "Tax Engine.",
        )
        self.assertEqual(
            product.icms_value,
            12.0,
            "The ICMS value does not match the standard in product from Automatic Tax "
            "Engine.",
        )

        self.assertEqual(
            product.ipi_percent,
            0.0,
            "The IPI percent does not match the standard in product from Automatic Tax "
            "Engine.",
        )
        self.assertEqual(
            product.ipi_value,
            0.0,
            "The IPI value does not match the standard in product from Automatic Tax "
            "Engine.",
        )

        self.assertEqual(
            product.pis_percent,
            0.65,
            "The PIS percent does not match the standard in product from Automatic Tax "
            "Engine.",
        )
        self.assertEqual(
            product.pis_value,
            0.65,
            "The PIS value does not match the standard in product from Automatic Tax "
            "Engine.",
        )

        self.assertEqual(
            product.cofins_percent,
            3.0,
            "The Cofins percent does not match the standard in product from Automatic "
            "Tax Engine.",
        )
        self.assertEqual(
            product.cofins_value,
            3.0,
            "The Cofins value does not match the standard in product from Automatic "
            "Tax Engine.",
        )

    def test_tax_engine_semi_automatic(self):
        """
        Unlike the default behavior of the system, when the 'tax_calc' is set to
            semi-automatic, the user must select the rates that will be used on
            that product and only then the system will calculate them.

        Used in return operations. Rates must be the same as those used in the
            input/output operation.
        """
        product = self.fiscal_document_demo_2.line_ids[0]

        self.assertEqual(
            product.icms_percent,
            12.0,
            "The ICMS percent does not match the standard in product from "
            "Semi-Automatic Tax Engine.",
        )
        self.assertEqual(
            product.icms_value,
            12.0,
            "The ICMS value does not match the standard in product from Semi-Automatic "
            "Tax Engine.",
        )

        self.assertEqual(
            product.ipi_percent,
            0.0,
            "The IPI percent does not match the standard in product from "
            "Semi-Automatic Tax Engine.",
        )
        self.assertEqual(
            product.ipi_value,
            0.0,
            "The IPI value does not match the standard in product from Semi-Automatic "
            "Tax Engine.",
        )

        self.assertEqual(
            product.pis_percent,
            0.65,
            "The PIS percent does not match the standard in product from "
            "Semi-Automatic Tax Engine.",
        )
        self.assertEqual(
            product.pis_value,
            0.65,
            "The PIS value does not match the standard in product from Semi-Automatic "
            "Tax Engine.",
        )

        self.assertEqual(
            product.cofins_percent,
            3.0,
            "The Cofins percent does not match the standard in product from "
            "Semi-Automatic Tax Engine.",
        )
        self.assertEqual(
            product.cofins_value,
            3.0,
            "The Cofins value does not match the standard in product from "
            "Semi-Automatic Tax Engine.",
        )

    # TODO
    def test_tax_engine_manual(self):
        pass
