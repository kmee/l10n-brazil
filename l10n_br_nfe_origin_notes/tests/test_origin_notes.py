# Copyright 2026 KMEE (https://www.kmee.com.br)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase


class TestOriginNotes(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.document = cls.env.ref(
            "l10n_br_nfe_origin_notes.demo_nfe_return_origin_notes"
        )

    def test_numbers_come_from_the_related_documents(self):
        self.assertEqual(self.document.origin_nfes_numbers, "123,4587")

    def test_numbers_go_to_the_additional_information(self):
        self.assertTrue(self.document.add_origin_nfe_to_xml)
        self.document._document_comment()
        self.assertIn(
            "NOTAS FISCAIS DE ORIGEM: 123,4587",
            self.document.customer_additional_data,
        )
        # Recomputing does not repeat the text
        self.document._document_comment()
        self.assertEqual(
            self.document.customer_additional_data.count("ORIGEM"),
            1,
        )

    def test_operation_off_keeps_the_text_out(self):
        self.document.fiscal_operation_id.add_origin_nfe_to_xml = False
        self.document._compute_add_origin_nfe_to_xml()
        self.document._document_comment()
        self.assertFalse(self.document.add_origin_nfe_to_xml)
        self.assertNotIn("ORIGEM", self.document.customer_additional_data or "")
