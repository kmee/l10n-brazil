# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import tagged

from .common import AccountMoveBRCommon


@tagged("post_install", "-at_install")
class TestInvoiceReport(AccountMoveBRCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.configure_normal_company_taxes()

    def test_invoice_report_fiscal_columns(self):
        invoice = self.init_invoice(
            "out_invoice",
            products=[self.product_a],
            document_type=self.env.ref("l10n_br_fiscal.document_55"),
            document_serie_id=self.empresa_lc_document_55_serie_1,
            fiscal_operation=self.env.ref("l10n_br_fiscal.fo_venda"),
            fiscal_operation_lines=[self.env.ref("l10n_br_fiscal.fo_venda_venda")],
        )
        invoice.action_post()
        line = invoice.invoice_line_ids
        self.env.flush_all()
        report = self.env["account.invoice.report"].search(
            [("move_id", "=", invoice.id)]
        )
        self.assertEqual(len(report), 1)
        self.assertEqual(
            report.document_type_id, self.env.ref("l10n_br_fiscal.document_55")
        )
        self.assertEqual(report.document_serie_id, self.empresa_lc_document_55_serie_1)
        self.assertEqual(report.issuer, invoice.fiscal_document_id.issuer)
        self.assertEqual(report.cfop_id, line.cfop_id)
        self.assertEqual(report.fiscal_operation_id, line.fiscal_operation_id)
        self.assertAlmostEqual(report.icms_value, line.icms_value)
