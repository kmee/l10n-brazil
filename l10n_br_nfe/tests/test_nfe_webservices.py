# Copyright (C) 2023 - TODAY Raphaël Valyi - Akretion
# Copyright (C) 2024 - TODAY Antônio S. P. Neto - Engenere
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).


import logging
from types import SimpleNamespace
from unittest import mock

from odoo.exceptions import UserError
from odoo.fields import Datetime

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    SITUACAO_EDOC_A_ENVIAR,
    SITUACAO_EDOC_AUTORIZADA,
    SITUACAO_EDOC_CANCELADA,
    SITUACAO_EDOC_ENVIADA,
    SITUACAO_EDOC_INUTILIZADA,
)
from odoo.addons.l10n_br_nfe.models.document import NFe

from .mock_utils import nfe_mock
from .test_nfe_serialize import TestNFeExport

_logger = logging.getLogger(__name__)


class TestNFeWebServices(TestNFeExport):
    @classmethod
    def setUpClass(cls):
        nfe_list = [
            {
                "record_ref": "l10n_br_nfe.demo_nfe_natural_icms_18_red_51_11",
                "xml_file": "NFe35200159594315000157550010000000022062777169.xml",
            },
        ]
        super().setUpClass(nfe_list)

    @nfe_mock(
        {
            "nfeAutorizacaoLote": "retEnviNFe/lote_recebido.xml",
            "nfeRetAutorizacaoLote": "retConsReciNFe/autorizada.xml",
            "nfeRecepcaoEvento": "retEnvEvento/nfe_cancelamento.xml",
        }
    )
    def test_enviar_e_cancelar(self):
        for nfe_data in self.nfe_list:
            nfe = nfe_data["nfe"]

            nfe.action_document_send()

            self.assertEqual(nfe.state_edoc, SITUACAO_EDOC_AUTORIZADA)

            cancel_wizard = (
                self.env["l10n_br_fiscal.document.cancel.wizard"]
                .with_context(active_model="l10n_br_fiscal.document", active_id=nfe.id)
                .create(
                    {"document_id": nfe.id, "justification": "Era apenas um teste."}
                )
            )
            cancel_wizard.doit()

            self.assertEqual(nfe.state_edoc, SITUACAO_EDOC_CANCELADA)
            self.assertIsNotNone(nfe.cancel_event_id)
            self.assertEqual(nfe.cancel_event_id.state, "done")
            self.assertEqual(nfe.cancel_event_id.status_code, "135")
            self.assertEqual(
                nfe.cancel_event_id.response, "Evento registrado e vinculado a NF-e"
            )
            self.assertEqual(
                Datetime.to_string(nfe.cancel_event_id.protocol_date),
                "2023-07-05 19:52:52",
            )

    @nfe_mock({"nfeInutilizacaoNF": "retInutNFe/nfe_inutilizacao.xml"})
    def test_inutilizar(self):
        nfe = self.nfe_list[0]["nfe"]
        inutilizar_wizard = (
            self.env["l10n_br_fiscal.invalidate.number.wizard"]
            .with_context(active_model="l10n_br_fiscal.document", active_id=nfe.id)
            .create({"document_id": nfe.id, "justification": "Era apenas um teste."})
        )
        inutilizar_wizard.doit()

    @nfe_mock(
        {
            "nfeAutorizacaoLote": "retEnviNFe/lote_recebido.xml",
            "nfeRetAutorizacaoLote": "retConsReciNFe/autorizada.xml",
        }
    )
    def test_nfe_consult_receipt(self):
        """
        Tests the asynchronous NFe transmission, separating the sending and
        the consultation into two distinct steps.
        """
        for nfe_data in self.nfe_list:
            nfe = nfe_data["nfe"]
            self.assertEqual(nfe.state_edoc, SITUACAO_EDOC_A_ENVIAR)
            with mock.patch.object(NFe, "make_pdf"):
                # enable skip receipt consultation during the send action
                self.env.company.nfe_separate_async_process = True
                nfe.action_document_send()
            # Document has been sent, but the receipt has not been consulted yet,
            # meaning the authorization protocol has not been received.
            self.assertEqual(nfe.state_edoc, SITUACAO_EDOC_ENVIADA)
            # Consult the receipt to receive the usage authorization.
            nfe._nfe_consult_receipt()
            self.assertEqual(nfe.state_edoc, SITUACAO_EDOC_AUTORIZADA)

    @nfe_mock(
        {
            "nfeAutorizacaoLote": "retEnviNFe/lote_recebido.xml",
            "nfeRetAutorizacaoLote": "retConsReciNFe/autorizada.xml",
        }
    )
    @mock.patch("odoo.addons.l10n_br_nfe.models.document._logger")
    def test_nfe_consult_receipt_without_nfe_saved(self, mock_logger):
        """
        Tests the NF-e processing result query after deleting the sent nfe xml.
        """
        for nfe_data in self.nfe_list:
            nfe = nfe_data["nfe"]
            self.assertEqual(nfe.state_edoc, SITUACAO_EDOC_A_ENVIAR)
            with mock.patch.object(NFe, "make_pdf"):
                # enable skip receipt consultation during the send action
                self.env.company.nfe_separate_async_process = True
                nfe.action_document_send()
            # Document has been sent, but the receipt has not been consulted yet,
            # meaning the authorization protocol has not been received.
            self.assertEqual(nfe.state_edoc, SITUACAO_EDOC_ENVIADA)
            # Consult the receipt to receive the usage authorization.

            # Erase the sending_file
            nfe.send_file_id = False
            self.assertFalse(nfe.send_file_id)

            nfe._nfe_consult_receipt()
            mock_logger.info.assert_called_with(
                "NF-e data not found when trying to assemble the "
                "xml with the authorization protocol (nfeProc)"
            )
            self.assertEqual(nfe.state_edoc, SITUACAO_EDOC_AUTORIZADA)

    @nfe_mock({"nfeConsultaNF": "retConsSitNFe/autorizado.xml"})
    def test_nfe_consult(self):
        for nfe_data in self.nfe_list:
            nfe = nfe_data["nfe"]
            self.assertEqual(nfe.state_edoc, SITUACAO_EDOC_A_ENVIAR)
            nfe._document_status()
            self.assertEqual(nfe.state_edoc, SITUACAO_EDOC_AUTORIZADA)

    def test_save_protocol_converts_to_utc(self):
        """dhRecbto with -03:00 offset must be stored as UTC (+3h)."""
        nfe = self.nfe_list[0]["nfe"]
        event_model = type(self.env["l10n_br_fiscal.event"])
        for dh_recbto, expected in (
            ("2026-10-13T08:45:28-03:00", "2026-10-13 11:45:28"),
            ("2026-10-13T08:45:28", "2026-10-13 08:45:28"),
        ):
            inf_prot = SimpleNamespace(
                dhRecbto=dh_recbto, cStat="100", xMotivo="ok", nProt="1"
            )
            with mock.patch.object(event_model, "set_done") as set_done:
                nfe._nfe_save_protocol(inf_prot)
            self.assertEqual(set_done.call_args.kwargs["protocol_date"], expected)

    # ---- inutilizacao of numbers that already exist as company documents ----

    def _set_authorization_protocol(self, nfe, protocol):
        """Make the document look (un)authorized at SEFAZ."""
        if not protocol:
            nfe.authorization_event_id = False
            return
        event = self.env["l10n_br_fiscal.event"].create_event_save_xml(
            company_id=nfe.company_id,
            environment="2",
            event_type="0",
            xml_file="<xml/>",
            document_id=nfe,
        )
        event.protocol_number = protocol
        nfe.authorization_event_id = event

    def _create_invalidate(self, number_start, number_end=None):
        nfe = self.nfe_list[0]["nfe"]
        return self.env["l10n_br_fiscal.invalidate.number"].create(
            {
                "company_id": nfe.company_id.id,
                "document_type_id": nfe.document_type_id.id,
                "document_serie_id": nfe.document_serie_id.id,
                "number_start": number_start,
                "number_end": number_end or number_start,
                "justification": "Numero nunca autorizado na SEFAZ.",
            }
        )

    def _inutilizar_and_count_docs(self, invalidate, nfe):
        domain = [
            ("company_id", "=", nfe.company_id.id),
            ("document_serie_id", "=", nfe.document_serie_id.id),
            ("document_number", "=", nfe.document_number),
        ]
        invalidate.action_invalidate()
        return self.env["l10n_br_fiscal.document"].search(domain)

    @nfe_mock({"nfeInutilizacaoNF": "retInutNFe/nfe_inutilizacao.xml"})
    def test_inutilizar_existing_cancelled_without_protocol(self):
        nfe = self.nfe_list[0]["nfe"]
        nfe.write({"state_edoc": SITUACAO_EDOC_CANCELADA})
        self._set_authorization_protocol(nfe, False)
        number = int(nfe.document_number)
        invalidate = self._create_invalidate(number)
        docs = self._inutilizar_and_count_docs(invalidate, nfe)
        self.assertEqual(invalidate.state, "done")
        self.assertEqual(docs, nfe)
        self.assertEqual(nfe.state_edoc, SITUACAO_EDOC_INUTILIZADA)
        self.assertEqual(nfe.invalidate_event_id, invalidate.authorization_event_id)

    @nfe_mock({"nfeInutilizacaoNF": "retInutNFe/nfe_inutilizacao.xml"})
    def test_inutilizar_existing_enviada(self):
        nfe = self.nfe_list[0]["nfe"]
        nfe.write({"state_edoc": SITUACAO_EDOC_ENVIADA})
        self._set_authorization_protocol(nfe, False)
        invalidate = self._create_invalidate(int(nfe.document_number))
        docs = self._inutilizar_and_count_docs(invalidate, nfe)
        self.assertEqual(docs, nfe)
        self.assertEqual(nfe.state_edoc, SITUACAO_EDOC_INUTILIZADA)

    def test_inutilizar_existing_authorized_blocked_before_sefaz(self):
        nfe = self.nfe_list[0]["nfe"]
        nfe.write({"state_edoc": SITUACAO_EDOC_AUTORIZADA})
        self._set_authorization_protocol(nfe, "135230000000002")
        invalidate = self._create_invalidate(int(nfe.document_number))
        with (
            mock.patch.object(type(invalidate), "_edoc_processor") as processor,
            self.assertRaises(UserError),
        ):
            invalidate.action_invalidate()
        processor.assert_not_called()
        self.assertEqual(invalidate.state, "draft")

    def test_inutilizar_cancelled_with_protocol_blocked_before_sefaz(self):
        nfe = self.nfe_list[0]["nfe"]
        nfe.write({"state_edoc": SITUACAO_EDOC_CANCELADA})
        self._set_authorization_protocol(nfe, "135230000000001")
        invalidate = self._create_invalidate(int(nfe.document_number))
        with (
            mock.patch.object(type(invalidate), "_edoc_processor") as processor,
            self.assertRaises(UserError),
        ):
            invalidate.action_invalidate()
        processor.assert_not_called()

    @nfe_mock({"nfeInutilizacaoNF": "retInutNFe/nfe_inutilizacao.xml"})
    def test_inutilizar_number_not_existing(self):
        nfe = self.nfe_list[0]["nfe"]
        number = int(nfe.document_number) + 5000
        invalidate = self._create_invalidate(number)
        invalidate.action_invalidate()
        created = self.env["l10n_br_fiscal.document"].search(
            [
                ("document_serie_id", "=", nfe.document_serie_id.id),
                ("document_number", "=", str(number)),
            ]
        )
        self.assertEqual(len(created), 1)
        self.assertEqual(created.state_edoc, SITUACAO_EDOC_INUTILIZADA)
        self.assertEqual(invalidate.state, "done")
