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
RET_TRIB = (
    b"<retTrib><vRetPIS>77.84</vRetPIS><vRetCOFINS>359.28</vRetCOFINS>"
    b"<vRetCSLL>119.76</vRetCSLL><vBCIRRF>11975.96</vBCIRRF>"
    b"<vIRRF>179.64</vIRRF><vBCRetPrev>5000.00</vBCRetPrev>"
    b"<vRetPrev>550.00</vRetPrev></retTrib>"
)
WITHHELD = 77.84 + 359.28 + 119.76 + 179.64 + 550.00


@tagged("post_install", "-at_install")
class TestImportWithholding(TransactionCase):
    """The withholdings of the total of the NF-e (retTrib) reach the document and
    its net amount payable. The group has no tax on the lines, so nothing is shared
    among them, and the installments of the file are what the file declared."""

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
        if "import_stock_entry_policy" in cls.company._fields:
            cls.company.import_stock_entry_policy = "none"

    def _content(self, with_withholding):
        with open(FIXTURE, "rb") as xml_file:
            content = xml_file.read()
        recipient = self.company.partner_id.cnpj_cpf_stripped
        content = FIXTURE_DEST.sub(rb"\1<CNPJ>%s</CNPJ>" % recipient.encode(), content)
        if with_withholding:
            content = content.replace(b"</ICMSTot>", b"</ICMSTot>" + RET_TRIB, 1)
            self.assertIn(b"<vRetPrev>", content)
        return content

    def _import_with_window(self, with_withholding):
        wizard = (
            self.env["l10n_br_fiscal.document.import.wizard"]
            .with_company(self.company)
            .create(
                {
                    "company_id": self.company.id,
                    "file": base64.b64encode(self._content(with_withholding)),
                    "allow_product_creation": True,
                }
            )
        )
        wizard._onchange_file()
        wizard.fiscal_operation_id = self.operation
        wizard.action_import_and_open_document()
        return wizard.document_id

    def _import_with_assistant(self, with_withholding):
        documents, errors, _warnings = (
            self.env["l10n_br_fiscal.document"]
            .with_company(self.company)
            .with_context(allow_product_creation=True)
            ._edi_import_files([("nfe.xml", self._content(with_withholding))])
        )
        self.assertFalse(errors)
        return documents

    def _check_withholding(self, document):
        self.assertTrue(document.import_withholding_declared)
        self.assertEqual(document.amount_pis_wh_value, 77.84)
        self.assertEqual(document.amount_cofins_wh_value, 359.28)
        self.assertEqual(document.amount_csll_wh_value, 119.76)
        self.assertEqual(document.amount_irpj_wh_base, 11975.96)
        self.assertEqual(document.amount_irpj_wh_value, 179.64)
        self.assertEqual(document.amount_inss_wh_base, 5000.0)
        self.assertEqual(document.amount_inss_wh_value, 550.0)
        self.assertAlmostEqual(document.amount_tax_withholding, WITHHELD, places=2)
        # nothing was shared among the lines
        self.assertFalse(sum(document.fiscal_line_ids.mapped("amount_tax_withholding")))

        gross, withholding, net = document._edi_payment_totals()
        self.assertAlmostEqual(withholding, WITHHELD, places=2)
        self.assertAlmostEqual(net, gross - WITHHELD, places=2)
        self.assertAlmostEqual(gross, 12108.10, places=2)
        self.assertIn("Withholdings", document.edi_payment_summary)

        # the installments are the ones of the file, not touched by the withholdings
        declared = sum(i.amount for i in document._edi_get_installments())
        self.assertAlmostEqual(declared, 12108.10, places=2)
        self.assertAlmostEqual(
            document._edi_installment_difference(), -WITHHELD, places=2
        )

    def test_the_window_keeps_the_withholdings_of_the_total(self):
        document = self._import_with_window(with_withholding=True)

        self._check_withholding(document)

    def test_the_assistant_keeps_the_withholdings_of_the_total(self):
        document = self._import_with_assistant(with_withholding=True)

        self._check_withholding(document)

    def test_the_withholdings_survive_a_new_sum_of_the_lines(self):
        document = self._import_with_assistant(with_withholding=True)

        document.fiscal_operation_id = self.operation
        total = document.fiscal_amount_total
        line = document.fiscal_line_ids[:1]

        line.quantity += 1
        document.flush_recordset()

        # the sum of the lines was computed again, the declared amounts stayed
        self.assertNotEqual(document.fiscal_amount_total, total)
        self.assertAlmostEqual(document.amount_tax_withholding, WITHHELD, places=2)
        self.assertEqual(document.amount_pis_wh_value, 77.84)
        self.assertEqual(document.amount_inss_wh_value, 550.0)

    def test_a_note_without_the_group_has_no_withholding(self):
        document = self._import_with_assistant(with_withholding=False)

        self.assertFalse(document.import_withholding_declared)
        self.assertEqual(document.amount_tax_withholding, 0.0)
        gross, withholding, net = document._edi_payment_totals()
        self.assertEqual(withholding, 0.0)
        self.assertEqual(gross, net)

    def test_the_warning_says_the_invoice_does_not_discount_the_withholdings(self):
        document = self._import_with_assistant(with_withholding=True)
        document.fiscal_operation_id = self.operation
        installments = [i.amount for i in document._edi_get_installments()]

        warning = document._edi_installment_warning()

        self.assertIn("does not discount them", warning)
        self.assertIn(f"{WITHHELD:.2f}", warning)
        # the installments of the file add up to what the invoice totals: no spread
        self.assertNotIn("spreads the difference", warning)
        self.assertAlmostEqual(
            sum(installments), document.fiscal_amount_total, places=2
        )
        self.assertIn("does not discount them", document.import_warning)
        # and the invoice does what the warning says
        document.action_import_create_products()
        move = self.env["account.move"].browse(
            document.action_generate_invoice()["res_id"]
        )
        due = move.line_ids.filtered(
            lambda line: line.account_id.account_type == "liability_payable"
        )
        self.assertAlmostEqual(sum(due.mapped("credit")), sum(installments), places=2)
        self.assertEqual(
            sorted(round(credit, 2) for credit in due.mapped("credit")),
            sorted(round(amount, 2) for amount in installments),
        )
