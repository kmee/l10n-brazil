# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests.common import TransactionCase


class TestDocumentImportWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env["res.company"].create(
            {
                "name": "Issuer Company Test",
                "vat": "47786619000137",
            }
        )

    def _wizard(self, issuer_cnpj):
        return self.env["l10n_br_fiscal.document.import.wizard"].create(
            {
                "company_id": self.company.id,
                "issuer_cnpj": issuer_cnpj,
            }
        )

    def test_fiscal_operation_type_out_when_issuer_cnpj_is_punctuated(self):
        wizard = self._wizard("47.786.619/0001-37")
        self.assertEqual(wizard.fiscal_operation_type, "out")

    def test_fiscal_operation_type_out_when_issuer_cnpj_is_unformatted(self):
        wizard = self._wizard("47786619000137")
        self.assertEqual(wizard.fiscal_operation_type, "out")

    def test_fiscal_operation_type_in_when_issuer_is_not_company(self):
        wizard = self._wizard("11.222.333/0001-81")
        self.assertEqual(wizard.fiscal_operation_type, "in")
