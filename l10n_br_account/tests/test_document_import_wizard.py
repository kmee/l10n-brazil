# Copyright (C) 2026 - TODAY KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

import base64

from odoo.exceptions import UserError
from odoo.tests import TransactionCase


class TestDocumentImportWizardAttachments(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.wizard = cls.env["l10n_br_fiscal.document.import.wizard"]

    def _attachment(self, name, mimetype):
        return self.env["ir.attachment"].create(
            {
                "name": name,
                "mimetype": mimetype,
                "datas": base64.b64encode(b"whatever"),
            }
        )

    def test_a_pdf_alone_is_refused_before_being_parsed(self):
        danfe = self._attachment("Nota Fiscal Eletronica.pdf", "application/pdf")

        with self.assertRaises(UserError) as error:
            self.wizard._get_importer_action(danfe)

        self.assertIn("Nota Fiscal Eletronica.pdf", str(error.exception))

    def test_an_xml_is_recognized_by_its_extension(self):
        attachment = self._attachment("nfe.XML", "application/octet-stream")

        self.assertTrue(self.wizard._is_xml_attachment(attachment))

    def test_an_xml_is_recognized_by_its_mimetype(self):
        attachment = self._attachment("nfe", "text/xml")

        self.assertTrue(self.wizard._is_xml_attachment(attachment))

    def test_a_pdf_is_not_taken_for_an_xml(self):
        attachment = self._attachment("danfe.pdf", "application/pdf")

        self.assertFalse(self.wizard._is_xml_attachment(attachment))
