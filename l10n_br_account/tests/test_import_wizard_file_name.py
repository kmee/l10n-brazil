# Copyright 2026 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
from unittest import mock

from odoo.tests.common import TransactionCase, tagged

WIZARD = "l10n_br_fiscal.document.import.wizard"


@tagged("post_install", "-at_install")
class TestImportWizardFileName(TransactionCase):
    def test_attachment_name_is_kept_as_the_wizard_file_name(self):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "35260812345678000195550010000049521000049521.xml",
                "datas": base64.b64encode(b"<nfeProc/>"),
            }
        )
        # The parsing belongs to the NF-e modules; here only the wizard
        # creation from the uploaded attachment matters.
        with mock.patch.object(
            type(self.env[WIZARD]), "_onchange_file", return_value=None
        ):
            action = self.env[WIZARD]._get_importer_action(attachment)
        wizard = self.env[WIZARD].browse(action["res_id"])
        self.assertEqual(wizard.file_name, attachment.name)
