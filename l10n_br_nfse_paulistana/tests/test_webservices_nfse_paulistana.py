# Copyright 2024 KMEE INFORMATICA LTDA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.tests import common

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    MODELO_FISCAL_NFSE,
    PROCESSADOR_OCA,
    SITUACAO_EDOC_AUTORIZADA,
    SITUACAO_EDOC_REJEITADA,
)


class TestL10nBrNfsePaulistana(common.TransactionCase):
    """Test class for Brazilian NFSe Paulistana integration."""

    def setUp(self):
        """Sets up test environment."""
        super().setUp()
        self.company = self.env.ref("base.main_company")  # Reference to main company
        self.company.provedor_nfse = "paulistana"  # Setting NFSe provider to paulistana
        self.nfse_demo = self.env.ref(
            "l10n_br_fiscal.demo_nfse_same_state"
        )  # NFSe demo document
        self.nfse_demo.document_number = "0001"  # Setting document number
        self.nfse_demo.rps_number = "0002"  # Setting RPS number
        self.nfse_demo.processador_edoc = (
            PROCESSADOR_OCA
        )  # Setting document processor to OCA
        self.nfse_demo.document_type_id.code = (
            MODELO_FISCAL_NFSE  # Setting document type to NFSe
        )

    @patch("odoo.addons.l10n_br_nfse_focus.models.document.requests.request")
    def test_serialize_nfse_paulistana(self, mock_post):
        """Tests serialization and processing of NFSe Paulistana."""
        # Configuring mock to simulate a successful response
        mock_post.return_value.status_code = 200  # Simulating successful POST request
        mock_post.return_value.json.return_value = {
            "status": "sucesso"
        }  # Mocking JSON response

        # Preparing document for serialization
        serialized_nfse = self.nfse_demo.serialize_nfse_paulistana()

        self.assertIsNotNone(
            serialized_nfse
        )  # Asserting that serialization is not None
        self.assertEqual(
            serialized_nfse.Cabecalho.CPFCNPJRemetente.CNPJ,
            self.company.cnpj_cpf,
            "The serialized CNPJ should match the company's CNPJ",
        )

    @patch("odoo.addons.l10n_br_nfse_focus.models.document.requests.request")
    def test_processar_nfse_paulistana(self, mock_request):
        """Tests NFSe Paulistana processing with mocked responses."""
        # Configuring mock to simulate different HTTP responses
        mock_request.return_value.status_code = (
            200
        )  # Simulating successful POST request
        mock_request.return_value.json.return_value = {
            "status": "success",
            "data": {
                "NumeroNFe": "00012345",
                "DataEmissaoRPS": "2024-01-01T00:00:00",
                "CodigoVerificacao": "123ABC",
            },
        }

        # Testing NFSe processing
        self.nfse_demo._eletronic_document_send()  # Sending the electronic document

        # Verifying if the document status has changed to authorized
        self.assertEqual(
            self.nfse_demo.state,
            SITUACAO_EDOC_AUTORIZADA,
            "The document state should be updated to 'authorized'",
        )
        self.assertEqual(
            self.nfse_demo.document_number,
            "00012345",
            "The document number should match the returned value from the provider",
        )
        self.assertEqual(
            self.nfse_demo.verify_code,
            "123ABC",
            "The verification code should match the returned value from the provider",
        )

    @patch("odoo.addons.l10n_br_nfse_focus.models.document.requests.request")
    def test_cancela_documento_paulistana(self, mock_delete):
        """Tests edoc cancellation for NFSe Paulistana with mocked DELETE request."""
        # Configuring mock to simulate a successful cancellation response
        mock_delete.return_value.status_code = 200
        mock_delete.return_value.json.return_value = {"status": "cancelado"}

        # Setting the document to be in an authorized state
        self.nfse_demo.state = SITUACAO_EDOC_AUTORIZADA
        self.nfse_demo.document_number = "00012345"
        self.nfse_demo.verify_code = "123ABC"

        # Attempting to cancel the document
        result = self.nfse_demo.cancel_document_paulistana()

        # Asserting that cancellation was successful
        self.assertTrue(result, "The cancellation should be successful.")
        self.assertEqual(
            self.nfse_demo.state,
            SITUACAO_EDOC_REJEITADA,
            "The document state should be updated to 'rejected' after cancellation",
        )

    @patch("odoo.addons.l10n_br_nfse_focus.models.document.requests.request")
    def test_document_status_paulistana(self, mock_get):
        """Tests querying edoc status for NFSe Paulistana with mocked GET request."""
        # Configuring mock to simulate a successful status query response
        mock_get.return_value.status_code = 200
        mock_get.return_value.json.return_value = {
            "status": "success",
            "data": {
                "NumeroNFe": "00012345",
                "DataEmissaoRPS": "2024-01-01T00:00:00",
                "CodigoVerificacao": "123ABC",
            },
        }

        # Querying the status of the NFSe
        status = self.nfse_demo._document_status()

        # Asserting that the status query was successful
        self.assertEqual(
            status,
            "Procesado com Sucesso",
            "The document status should be 'Processed with Success'",
        )
        self.assertEqual(
            self.nfse_demo.state,
            SITUACAO_EDOC_AUTORIZADA,
            "The document state should be updated to 'authorized'",
        )
