# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestMoveDocumentOnWrite(TransactionCase):
    """A move saved without document type gets its fiscal document on write."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.env = cls.env(
            context=dict(cls.env.context, allowed_company_ids=cls.company.ids)
        )
        cls.env.user.company_id = cls.company
        cls.partner = cls.env.ref("l10n_br_base.res_partner_cliente1_sp")
        cls.document_type = cls.env.ref("l10n_br_fiscal.document_55")
        cls.operation = cls.env.ref("l10n_br_fiscal.fo_compras")

    def _create_bill(self, **vals):
        return self.env["account.move"].create(
            dict(
                move_type="in_invoice",
                partner_id=self.partner.id,
                company_id=self.company.id,
                **vals,
            )
        )

    def test_bill_saved_without_type_accepts_type_later(self):
        bill = self._create_bill()
        self.assertFalse(bill.fiscal_document_id)

        bill.write(
            {
                "document_type_id": self.document_type.id,
                "fiscal_operation_id": self.operation.id,
            }
        )

        document = bill.fiscal_document_id
        self.assertTrue(document)
        self.assertEqual(bill.document_type_id, self.document_type)
        self.assertEqual(document.document_type_id, self.document_type)
        self.assertEqual(document.fiscal_operation_id, self.operation)
        self.assertEqual(document.partner_id, self.partner)
        self.assertEqual(document.company_id, self.company)
        # vendor bill: the document is issued by the partner
        self.assertEqual(document.issuer, "partner")

    def test_invoice_saved_without_type_is_issued_by_company(self):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner.id,
                "company_id": self.company.id,
            }
        )
        self.assertFalse(invoice.fiscal_document_id)

        invoice.write({"document_type_id": self.document_type.id})

        self.assertEqual(invoice.fiscal_document_id.issuer, "company")

    def test_bill_with_fiscal_document_is_untouched(self):
        bill = self._create_bill(
            document_type_id=self.document_type.id,
            fiscal_operation_id=self.operation.id,
        )
        document = bill.fiscal_document_id
        self.assertTrue(document)

        Document = self.env["l10n_br_fiscal.document"]
        count_before = Document.search_count([])

        bill.write({"document_type_id": self.document_type.id})

        self.assertEqual(bill.fiscal_document_id, document)
        self.assertEqual(Document.search_count([]), count_before)

    def test_write_without_type_keeps_bill_without_document(self):
        bill = self._create_bill()
        bill.write({"ref": "no document type"})
        self.assertFalse(bill.fiscal_document_id)
