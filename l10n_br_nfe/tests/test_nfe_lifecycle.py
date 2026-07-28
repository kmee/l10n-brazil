# Copyright 2026 KMEE (Luis Felipe Mileo <mileo@kmee.com.br>)
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).
"""Characterization tests for the NF-e / NFC-e electronic document lifecycle.

These tests are a safety net, not a specification. They freeze the *observable*
behaviour of the current (legacy) workflow engine of ``l10n_br_fiscal_edi``
(``_change_state``, the ``_exec_before_SITUACAO_EDOC_*`` /
``_exec_after_SITUACAO_EDOC_*`` hooks and the ``action_document_*`` entry
points) as consumed by ``l10n_br_nfe``.

Whenever the current behaviour looks wrong, the test still asserts what the
code does today and the oddity is flagged with a
``# NOTE: current behavior -- see #4629 discussion`` comment, so that the
workflow engine refactor (and the later migration of this module to the new
API) can be reviewed against a known baseline instead of against intuition.

No network access: every SEFAZ round trip goes through the XML fixtures under
``tests/mocks`` via the shared ``nfe_mock`` helper.
"""

from unittest import mock

import nfelib
import pkg_resources
from erpbrasil.assinatura import misc
from nfelib.nfe.bindings.v4_0.leiaute_nfe_v4_00 import TnfeProc

from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    SITUACAO_EDOC_A_ENVIAR,
    SITUACAO_EDOC_AUTORIZADA,
    SITUACAO_EDOC_CANCELADA,
    SITUACAO_EDOC_DENEGADA,
    SITUACAO_EDOC_EM_DIGITACAO,
    SITUACAO_EDOC_ENVIADA,
    SITUACAO_EDOC_INUTILIZADA,
    SITUACAO_EDOC_REJEITADA,
    SITUACAO_FISCAL_CANCELADO,
)
from odoo.addons.l10n_br_nfe.models.document import NFe

from .mock_utils import NFeMock, nfe_mock
from .test_nfe_serialize import TestNFeExport

NFE_LC_DEMO = "l10n_br_nfe.demo_nfe_natural_icms_18_red_51_11"
NFE_LC_DEMO_2 = "l10n_br_nfe.demo_nfe_natural_icms_7_resale"
NFCE_DEMO = "l10n_br_nfe.demo_nfce_same_state"

# Sample NF-e shipped by nfelib, used to build a third party (imported) document.
NFELIB_SAMPLE = (
    "nfe",
    "samples",
    "v4_0",
    "leiauteNFe",
    "35180834128745000152550010000474281920007498-nfe.xml",
)

# The demo companies keep `nfe_enable_sync_transmission` disabled, so the NF-e
# processor built by _edoc_processor() is *asynchronous*: erpbrasil expects the
# authorization webservice to answer with a batch receipt (cStat 103 + infRec)
# and then reads the outcome from the receipt consult. Answering
# `nfeAutorizacaoLote` with a synchronous retEnviNFe (cStat 104 + protNFe and no
# infRec) makes erpbrasil blow up in `_aguarda_tempo_medio` with
# `AttributeError: 'NoneType' object has no attribute 'tMed'`, so the
# retEnviNFe/autorizada.xml and retEnviNFe/denegada.xml fixtures can only be
# used for NFC-e (whose processor is synchronous).
NFE_ASYNC_AUTHORIZED = {
    "nfeAutorizacaoLote": "retEnviNFe/lote_recebido.xml",
    "nfeRetAutorizacaoLote": "retConsReciNFe/autorizada.xml",
}
NFE_ASYNC_DENIED = {
    "nfeAutorizacaoLote": "retEnviNFe/lote_recebido.xml",
    "nfeRetAutorizacaoLote": "retConsReciNFe/uso_denegado.xml",
}
NFE_REJECTED = {"nfeAutorizacaoLote": "retEnviNFe/rejeitada.xml"}


class RecordingNFeMock(NFeMock):
    """``NFeMock`` that also records which SEFAZ webservices were called.

    Several lifecycle branches are silent no-ops today (a resend that is
    dropped, a send blocked by a XML schema error). The stock ``nfe_mock``
    helper cannot tell "not called at all" from "called and answered by a
    fixture", so these tests need the call log to prove the difference.
    """

    def __init__(self, xml_soap_paths=None):
        super().__init__(xml_soap_paths)
        self.calls = []

    def custom_send(self, operacao, *args, **kwargs):
        self.calls.append(operacao)
        return super().custom_send(operacao, *args, **kwargs)


class TestNFeLifecycleRejection(TestNFeExport):
    """Rejection -> correction -> resend."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass(nfe_list=[{"record_ref": NFE_LC_DEMO}])
        cls.nfe = cls.nfe_list[0]["nfe"]

    def _reject(self):
        with nfe_mock(NFE_REJECTED):
            self.nfe.action_document_send()

    def test_send_rejected_by_sefaz_sets_rejeitada(self):
        """Batch refused (cStat 225): a_enviar -> rejeitada, status fields filled."""
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_A_ENVIAR)

        self._reject()

        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_REJEITADA)
        self.assertEqual(self.nfe.status_code, "225")
        self.assertEqual(self.nfe.status_name, "Rejeicao: Falha no Schema XML da NFe")

    def test_resend_from_rejeitada_is_a_silent_noop(self):
        """Resending straight from rejeitada does not transmit anything."""
        self._reject()
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_REJEITADA)

        recorder = RecordingNFeMock(NFE_ASYNC_AUTHORIZED)
        with recorder:
            self.nfe.action_document_send()

        # NOTE: current behavior -- see #4629 discussion.
        # _action_document_send() does accept `rejeitada` in its filter, but
        # l10n_br_nfe._eletronic_document_send() bails out with a plain
        # `return` for any state other than `a_enviar`/`enviada`. So the
        # resend is dropped without a single webservice call and without any
        # feedback to the user.
        self.assertEqual(recorder.calls, [])
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_REJEITADA)

    def test_rejeitada_recovery_via_back2draft_confirm_and_resend(self):
        """The real fix path is rejeitada -> em_digitacao -> a_enviar -> autorizada."""
        self._reject()
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_REJEITADA)

        self.nfe.action_document_back2draft()
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_EM_DIGITACAO)
        self.assertFalse(self.nfe.xml_error_message)

        self.nfe.action_document_confirm()
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_A_ENVIAR)

        with nfe_mock(NFE_ASYNC_AUTHORIZED), mock.patch.object(NFe, "make_pdf"):
            self.nfe.action_document_send()

        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_AUTORIZADA)
        self.assertEqual(self.nfe.status_code, "100")

    def test_rejeitada_to_rejeitada_is_an_allowed_transition(self):
        """A rejected document may be rejected again (self loop in WORKFLOW_EDOC)."""
        self._reject()

        self.assertTrue(self.nfe._change_state(SITUACAO_EDOC_REJEITADA))
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_REJEITADA)

    def test_send_from_em_digitacao_does_not_transmit(self):
        """_action_document_send only transmits a_enviar/enviada/rejeitada docs."""
        self.nfe.action_document_back2draft()
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_EM_DIGITACAO)

        recorder = RecordingNFeMock(NFE_ASYNC_AUTHORIZED)
        with recorder:
            self.nfe.action_document_send()

        self.assertEqual(recorder.calls, [])
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_EM_DIGITACAO)


class TestNFeLifecycleAsync(TestNFeExport):
    """Asynchronous batch transmission and receipt (lot_receipt_number) consult."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass(nfe_list=[{"record_ref": NFE_LC_DEMO}])
        cls.nfe = cls.nfe_list[0]["nfe"]

    def _send_async(self, receipt_fixture="retConsReciNFe/autorizada.xml"):
        # NOTE: current behavior -- _nfe_send_for_authorization() reads
        # `self.env.company.nfe_separate_async_process`, i.e. the *user*
        # company and not `self.company_id`, so the flag must be set on
        # env.company for the two step flow to kick in.
        self.env.company.nfe_separate_async_process = True
        with nfe_mock(
            {
                "nfeAutorizacaoLote": "retEnviNFe/lote_recebido.xml",
                "nfeRetAutorizacaoLote": receipt_fixture,
            }
        ), mock.patch.object(NFe, "make_pdf"):
            self.nfe.action_document_send()

    def test_async_send_stops_at_enviada_with_receipt_number(self):
        """Async batch (cStat 103): a_enviar -> enviada, receipt stored, no protocol."""
        self._send_async()

        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_ENVIADA)
        self.assertEqual(
            self.nfe.authorization_event_id.lot_receipt_number, "423002202113232"
        )
        self.assertFalse(self.nfe.authorization_protocol)

    def test_async_send_writes_enviada_bypassing_change_state(self):
        """The a_enviar -> enviada hop is a raw write, it never calls _change_state."""
        document_cls = type(self.nfe)
        original_change_state = document_cls._change_state
        calls = []

        def tracking_change_state(records, new_state, force_change=False):
            calls.append((records, new_state))
            return original_change_state(records, new_state, force_change)

        self.env.company.nfe_separate_async_process = True
        with nfe_mock(NFE_ASYNC_AUTHORIZED), mock.patch.object(
            document_cls, "_change_state", tracking_change_state
        ):
            self.nfe.action_document_send()

        # _document_send() always calls _change_state() on the (here empty)
        # set of non electronic documents, so only the calls carrying actual
        # records are relevant.
        effective_calls = [state for records, state in calls if records]

        # NOTE: current behavior -- see #4629 discussion.
        # _nfe_process_send_asynchronous() assigns `self.state_edoc = "enviada"`
        # directly, so neither the transition matrix nor the before/after hooks
        # run for this state change.
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_ENVIADA)
        self.assertEqual(effective_calls, [])

    def test_second_send_from_enviada_consults_receipt_and_authorizes(self):
        """Sending again from enviada consults the receipt instead of retransmitting."""
        self._send_async()
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_ENVIADA)

        recorder = RecordingNFeMock(NFE_ASYNC_AUTHORIZED)
        with recorder, mock.patch.object(NFe, "make_pdf"):
            self.nfe.action_document_send()

        self.assertNotIn("nfeAutorizacaoLote", recorder.calls)
        self.assertIn("nfeRetAutorizacaoLote", recorder.calls)
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_AUTORIZADA)
        self.assertEqual(self.nfe.status_code, "100")

    def test_explicit_receipt_consult_authorizes(self):
        """_nfe_consult_receipt() moves enviada -> autorizada using the stored nRec."""
        self._send_async()
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_ENVIADA)

        with nfe_mock(
            {"nfeRetAutorizacaoLote": "retConsReciNFe/autorizada.xml"}
        ), mock.patch.object(NFe, "make_pdf"):
            self.nfe._nfe_consult_receipt()

        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_AUTORIZADA)
        self.assertTrue(self.nfe.authorization_protocol)

    def test_receipt_consult_returning_denial(self):
        """A denied protocol on the receipt consult moves enviada -> denegada."""
        self._send_async(receipt_fixture="retConsReciNFe/uso_denegado.xml")
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_ENVIADA)

        with nfe_mock({"nfeRetAutorizacaoLote": "retConsReciNFe/uso_denegado.xml"}):
            self.nfe._nfe_consult_receipt()

        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_DENEGADA)
        self.assertEqual(self.nfe.status_code, "303")


class TestNFeLifecycleXmlValidation(TransactionCase):
    """XML schema validation failure and the recovery path around it."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.company = cls.env.ref("l10n_br_base.empresa_lucro_presumido")
        cls.env.user.company_ids += cls.company
        cls.env.user.company_id = cls.company
        cls.partner = cls.env.ref("l10n_br_base.res_partner_address_ak3")
        cls.valid_zip = cls.partner.zip
        cls.document = cls.env["l10n_br_fiscal.document"].create(
            {
                "partner_id": cls.partner.id,
                "document_type_id": cls.env.ref("l10n_br_fiscal.document_55").id,
                "fiscal_operation_id": cls.env.ref("l10n_br_fiscal.fo_venda").id,
            }
        )
        cls.env["l10n_br_fiscal.document.line"].create(
            {
                "document_id": cls.document.id,
                "company_id": cls.document.company_id.id,
                "partner_id": cls.document.partner_id.id,
                "fiscal_operation_type": cls.document.fiscal_operation_type,
                "fiscal_operation_id": cls.document.fiscal_operation_id.id,
                "product_id": cls.env.ref("product.product_product_4c").id,
            }
        )

    def _break_partner_zip(self):
        self.partner.write({"zip": "XoQC@33278"})

    def test_invalid_xml_still_reaches_a_enviar(self):
        """A schema error does not veto the confirmation: doc lands in a_enviar."""
        self._break_partner_zip()

        self.document.action_document_confirm()

        # NOTE: current behavior -- see #4629 discussion.
        # _document_export() only records the schema errors in
        # xml_error_message; _exec_before_SITUACAO_EDOC_A_ENVIAR still returns
        # True, so the document is confirmed with an invalid XML attached.
        self.assertEqual(self.document.state_edoc, SITUACAO_EDOC_A_ENVIAR)
        self.assertIn("CEP", self.document.xml_error_message)

    def test_invalid_xml_blocks_transmission_without_error(self):
        """With xml_error_message set, sending is a silent no-op (no SEFAZ call)."""
        self._break_partner_zip()
        self.document.action_document_confirm()
        self.assertTrue(self.document.xml_error_message)

        recorder = RecordingNFeMock(NFE_ASYNC_AUTHORIZED)
        with recorder:
            self.document.action_document_send()

        # NOTE: current behavior -- see #4629 discussion. No UserError, no
        # state change, no webservice call: the only feedback is the
        # xml_error_message field still being filled.
        self.assertEqual(recorder.calls, [])
        self.assertEqual(self.document.state_edoc, SITUACAO_EDOC_A_ENVIAR)
        self.assertIn("CEP", self.document.xml_error_message)

    def test_invalid_xml_recovery_via_back2draft(self):
        """back2draft clears the schema errors and the fixed doc confirms clean."""
        self._break_partner_zip()
        self.document.action_document_confirm()
        self.assertIn("CEP", self.document.xml_error_message)

        self.document.action_document_back2draft()

        self.assertEqual(self.document.state_edoc, SITUACAO_EDOC_EM_DIGITACAO)
        self.assertFalse(self.document.xml_error_message)
        self.assertFalse(self.document.file_report_id)

        self.partner.write({"zip": self.valid_zip})
        self.document.action_document_confirm()

        self.assertEqual(self.document.state_edoc, SITUACAO_EDOC_A_ENVIAR)
        self.assertNotIn("CEP", self.document.xml_error_message or "")


class TestNFCeLifecycleContingency(TestNFeExport):
    """NFC-e off-line contingency and the recovery once SEFAZ is back."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass(nfe_list=[])
        cls.nfce = cls.env.ref(NFCE_DEMO)
        certificate = cls.env["l10n_br_fiscal.certificate"].create(
            {
                "type": "nf-e",
                "subtype": "a1",
                "password": "123456",
                "file": misc.create_fake_certificate_file(
                    valid=True,
                    passwd="123456",
                    issuer="EMISSOR A TESTE",
                    country="BR",
                    subject="CERTIFICADO VALIDO TESTE",
                ),
            }
        )
        cls.nfce.company_id.certificate_nfe_id = certificate
        cls.nfce.company_id.nfce_csc_token = "DUMMY"
        cls.nfce.company_id.nfce_csc_code = "DUMMY"
        cls.prepare_test_nfe(cls.nfce)

    def _fall_into_contingency(self):
        with nfe_mock({"nfeAutorizacaoLote": "retEnviNFe/servico_paralizado.xml"}):
            self.nfce.action_document_send()

    def test_contingency_keeps_a_enviar_and_switches_tpemis(self):
        """Service down (cStat 108): NFC-e stays a_enviar and flips tpEmis to 9."""
        key_before = self.nfce.document_key
        # position 34 of the access key holds tpEmis (1 = normal emission)
        self.assertEqual(key_before[34], "1")

        self._fall_into_contingency()

        self.assertEqual(self.nfce.state_edoc, SITUACAO_EDOC_A_ENVIAR)
        self.assertEqual(self.nfce.nfe_transmission, "9")
        self.assertEqual(self.nfce.nfe40_tpEmis, "9")
        self.assertTrue(self.nfce.nfe40_dhCont)
        self.assertEqual(
            self.nfce.nfe40_xJust, "Sem comunicação com o servidor da Sefaz."
        )
        # the off-line QR Code is generated locally, no SEFAZ round trip
        with nfe_mock({}):
            self.assertIsNotNone(self.nfce.get_nfce_qrcode())

    def test_contingency_does_not_regenerate_the_access_key(self):
        """The access key keeps tpEmis=1 even after switching to contingency."""
        key_before = self.nfce.document_key

        self._fall_into_contingency()

        # NOTE: current behavior -- see #4629 discussion.
        # _update_nfce_for_offline_contingency() only writes nfe_transmission,
        # dhCont and xJust. _generate_key() is not called again (and
        # _document_number() would skip it anyway since document_key is set),
        # so the XML now declares tpEmis=9 while chNFe still encodes tpEmis=1.
        self.assertEqual(self.nfce.document_key, key_before)
        self.assertEqual(self.nfce.document_key[34], "1")
        self.assertEqual(self.nfce.nfe40_tpEmis, "9")

    def test_recovery_after_contingency_authorizes(self):
        """Once SEFAZ is back, a new send authorizes the contingency NFC-e."""
        self._fall_into_contingency()
        self.assertEqual(self.nfce.nfe_transmission, "9")

        with nfe_mock({"nfeAutorizacaoLote": "retEnviNFe/autorizada.xml"}):
            self.nfce.action_document_send()

        self.assertEqual(self.nfce.state_edoc, SITUACAO_EDOC_AUTORIZADA)
        self.assertEqual(self.nfce.status_code, "100")
        # NOTE: current behavior -- nothing resets nfe_transmission back to
        # "1", the authorized document stays flagged as off-line contingency.
        self.assertEqual(self.nfce.nfe_transmission, "9")


class TestNFeLifecycleImportedDocument(TransactionCase):
    """Third party (imported) documents: guards and shortcuts of the workflow."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        nfe_stream = pkg_resources.resource_stream(
            nfelib.__name__, "/".join(NFELIB_SAMPLE)
        )
        binding = TnfeProc.from_xml(nfe_stream.read().decode())
        cls.imported = cls.env["l10n_br_fiscal.document"].import_binding_nfe(
            binding, edoc_type="in", dry_run=False
        )

    def test_imported_document_is_flagged_and_issued_by_the_partner(self):
        """Importing an inbound NF-e sets imported_document and issuer=partner."""
        self.assertTrue(self.imported.imported_document)
        self.assertEqual(self.imported.issuer, "partner")
        self.assertEqual(self.imported.fiscal_operation_type, "in")
        self.assertEqual(self.imported.state_edoc, SITUACAO_EDOC_EM_DIGITACAO)

    def test_imported_document_correction_is_refused(self):
        """A correction letter is refused on a document issued by a third party."""
        with self.assertRaises(UserError):
            self.imported.action_document_correction()

    def test_imported_document_invalidate_is_refused(self):
        """Number invalidation is refused on a document issued by a third party."""
        with self.assertRaises(UserError):
            self.imported.action_document_invalidate()

    def test_imported_document_cancel_bypasses_wizard_and_workflow(self):
        """Cancelling a third party document just writes state_edoc=cancelada."""
        result = self.imported.action_document_cancel()

        # NOTE: current behavior -- see #4629 discussion.
        # _action_document_cancel() takes the `else` branch for issuer=partner
        # and assigns state_edoc directly: no wizard, no justification, no
        # cancel event, no transition check and no before/after hooks.
        self.assertIsNone(result)
        self.assertEqual(self.imported.state_edoc, SITUACAO_EDOC_CANCELADA)
        self.assertFalse(self.imported.cancel_event_id)
        self.assertFalse(self.imported.cancel_reason)

    def test_imported_document_confirm_skips_a_enviar_and_numbering(self):
        """Confirming a third party document jumps straight to autorizada."""
        number_before = self.imported.document_number
        key_before = self.imported.document_key

        self.imported.action_document_confirm()

        # _document_confirm() sends issuer=partner documents directly to
        # `autorizada`, so _document_number() (numbering, serie and access key
        # generation) is never reached for imported documents.
        self.assertEqual(self.imported.state_edoc, SITUACAO_EDOC_AUTORIZADA)
        self.assertEqual(self.imported.document_number, number_before)
        self.assertEqual(self.imported.document_key, key_before)

    def test_imported_document_number_is_a_noop(self):
        """_document_number() does nothing when the issuer is not the company."""
        number_before = self.imported.document_number
        key_before = self.imported.document_key

        self.imported._document_number()

        self.assertEqual(self.imported.document_number, number_before)
        self.assertEqual(self.imported.document_key, key_before)

    def test_imported_document_back2draft_bypasses_the_transition_matrix(self):
        """back2draft on a third party document writes state_edoc directly."""
        self.imported.action_document_confirm()
        self.assertEqual(self.imported.state_edoc, SITUACAO_EDOC_AUTORIZADA)

        self.imported.action_document_back2draft()

        # NOTE: current behavior -- see #4629 discussion.
        # document_back2draft() only routes through _change_state() when
        # issuer == company. For issuer=partner it assigns state_edoc, so
        # autorizada -> em_digitacao (forbidden by WORKFLOW_EDOC and refused
        # for own documents) silently succeeds here.
        self.assertEqual(self.imported.state_edoc, SITUACAO_EDOC_EM_DIGITACAO)


class TestNFeLifecycleDenial(TestNFeExport):
    """Denial (denegada) of an own NF-e."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass(nfe_list=[{"record_ref": NFE_LC_DEMO}])
        cls.nfe = cls.nfe_list[0]["nfe"]

    def test_send_denied_sets_denegada(self):
        """A denied protocol (cStat 303) moves the NF-e to denegada in one send."""
        with nfe_mock(NFE_ASYNC_DENIED):
            self.nfe.action_document_send()

        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_DENEGADA)
        self.assertEqual(self.nfe.status_code, "303")

    def test_denial_only_calls_the_private_hook(self):
        """Denial runs _exec_after_SITUACAO_EDOC_DENEGADA, not the public hook."""
        document_cls = type(self.nfe)
        with nfe_mock(NFE_ASYNC_DENIED), mock.patch.object(
            document_cls, "_exec_after_SITUACAO_EDOC_DENEGADA"
        ) as private_hook, mock.patch.object(
            document_cls, "exec_after_SITUACAO_EDOC_DENEGADA"
        ) as public_hook:
            self.nfe.action_document_send()

        # NOTE: current behavior -- see #4629 discussion.
        # _after_change_state() dispatches to the *private*
        # _exec_after_SITUACAO_EDOC_DENEGADA. The public
        # exec_after_SITUACAO_EDOC_DENEGADA (see PR #3272), which l10n_br_account
        # overrides to cancel the related account.move, is never reached by the
        # engine: it is only invoked when some other code calls it explicitly.
        self.assertTrue(private_hook.called)
        self.assertFalse(public_hook.called)
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_DENEGADA)

    def test_denegada_is_a_terminal_state(self):
        """No transition out of denegada is declared in WORKFLOW_EDOC."""
        with nfe_mock(NFE_ASYNC_DENIED):
            self.nfe.action_document_send()
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_DENEGADA)

        self.assertFalse(
            self.nfe._avaliable_transition(
                SITUACAO_EDOC_DENEGADA, SITUACAO_EDOC_EM_DIGITACAO
            )
        )
        with self.assertRaises(UserError):
            self.nfe.action_document_back2draft()


class TestNFeLifecycleBack2Draft(TestNFeExport):
    """back2draft from every reachable state."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass(nfe_list=[{"record_ref": NFE_LC_DEMO}])
        cls.nfe = cls.nfe_list[0]["nfe"]

    def test_back2draft_from_a_enviar_clears_error_fields(self):
        """a_enviar -> em_digitacao, wiping xml_error_message and file_report_id."""
        self.nfe.xml_error_message = "previous schema error"

        self.nfe.action_document_back2draft()

        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_EM_DIGITACAO)
        self.assertFalse(self.nfe.xml_error_message)
        self.assertFalse(self.nfe.file_report_id)

    def test_back2draft_from_rejeitada_clears_error_fields(self):
        """rejeitada -> em_digitacao, wiping xml_error_message and file_report_id."""
        with nfe_mock({"nfeAutorizacaoLote": "retEnviNFe/rejeitada.xml"}):
            self.nfe.action_document_send()
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_REJEITADA)
        self.nfe.xml_error_message = "previous schema error"

        self.nfe.action_document_back2draft()

        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_EM_DIGITACAO)
        self.assertFalse(self.nfe.xml_error_message)
        self.assertFalse(self.nfe.file_report_id)

    def test_back2draft_is_skipped_when_already_em_digitacao(self):
        """_action_document_back2draft filters out documents already in draft."""
        self.nfe.action_document_back2draft()
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_EM_DIGITACAO)
        self.nfe.xml_error_message = "previous schema error"

        self.nfe.action_document_back2draft()

        self.assertEqual(self.nfe.xml_error_message, "previous schema error")

    def test_back2draft_with_sped_cancelled_fiscal_state(self):
        """The SPED guard blocks back2draft on a SPED-cancelled document."""
        self.nfe.state_fiscal = SITUACAO_FISCAL_CANCELADO

        # NOTE: current behavior -- see #4629 discussion.
        # _exec_after_SITUACAO_EDOC_EM_DIGITACAO() does `raise (_("..."))`, i.e.
        # it raises a plain string, which Python reports as a TypeError instead
        # of the intended UserError: the end user gets "exceptions must derive
        # from BaseException" rather than the fiscal explanation. What this
        # characterization pins down is the GUARD (the back2draft must be
        # blocked), not the broken exception type, so a future engine fixing
        # it to UserError keeps this test green.
        try:
            self.nfe.action_document_back2draft()
        except (TypeError, UserError):
            state_when_guard_fired = self.nfe.state_edoc
        else:
            self.fail("the SPED guard should have blocked the back2draft")

        # The guard lives in the *after* hook, so _change_state() has already
        # written the new state when it fires. Only the transaction rollback
        # (the exception reaching the RPC layer, or the savepoint of
        # assertRaises in a test) undoes it.
        self.assertEqual(state_when_guard_fired, SITUACAO_EDOC_EM_DIGITACAO)

    def test_back2draft_from_autorizada_is_refused(self):
        """autorizada -> em_digitacao raises UserError after wiping the fields."""
        with nfe_mock(NFE_ASYNC_AUTHORIZED), mock.patch.object(NFe, "make_pdf"):
            self.nfe.action_document_send()
        self.assertEqual(self.nfe.state_edoc, SITUACAO_EDOC_AUTORIZADA)
        self.nfe.xml_error_message = "previous schema error"

        # NOTE: current behavior -- see #4629 discussion.
        # document_back2draft() clears xml_error_message and file_report_id
        # *before* validating the transition, so the fields are already wiped
        # when the UserError is raised. It only becomes visible to a caller
        # that catches the error and keeps working in the same transaction.
        try:
            self.nfe.action_document_back2draft()
        except UserError:
            error_message_when_refused = self.nfe.xml_error_message
            state_when_refused = self.nfe.state_edoc
        else:
            self.fail("back2draft from autorizada should have been refused")

        self.assertFalse(error_message_when_refused)
        self.assertEqual(state_when_refused, SITUACAO_EDOC_AUTORIZADA)


class TestNFeLifecycleChangeState(TestNFeExport):
    """_change_state() semantics: recordset loop, veto, force and transitions."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass(
            nfe_list=[{"record_ref": NFE_LC_DEMO}, {"record_ref": NFE_LC_DEMO_2}]
        )
        cls.doc_a = cls.nfe_list[0]["nfe"]
        cls.doc_b = cls.nfe_list[1]["nfe"]

    def test_change_state_iterates_the_whole_recordset(self):
        """_change_state() on a 2 record set moves both and returns True."""
        documents = self.doc_a | self.doc_b
        self.assertEqual(len(documents), 2)

        self.assertTrue(documents._change_state(SITUACAO_EDOC_REJEITADA))

        self.assertEqual(self.doc_a.state_edoc, SITUACAO_EDOC_REJEITADA)
        self.assertEqual(self.doc_b.state_edoc, SITUACAO_EDOC_REJEITADA)

    def test_change_state_aborts_on_the_first_invalid_transition(self):
        """An invalid transition aborts the loop with the previous records moved."""
        self.doc_b._change_state(SITUACAO_EDOC_REJEITADA)
        # browse() keeps the given order, so doc_a is processed first and
        # doc_b (rejeitada -> enviada is not in WORKFLOW_EDOC) is the one
        # that blows up.
        documents = self.env["l10n_br_fiscal.document"].browse(
            [self.doc_a.id, self.doc_b.id]
        )
        self.assertEqual(list(documents), [self.doc_a, self.doc_b])

        try:
            documents._change_state(SITUACAO_EDOC_ENVIADA)
        except UserError:
            state_a_when_aborted = self.doc_a.state_edoc
            state_b_when_aborted = self.doc_b.state_edoc
        else:
            self.fail("rejeitada -> enviada should have been refused")

        # NOTE: current behavior -- see #4629 discussion. The loop has no
        # all-or-nothing semantics: doc_a is already `enviada` when doc_b
        # aborts the call. Only the transaction rollback undoes it, so any
        # caller that catches the UserError keeps a half applied batch.
        self.assertEqual(state_a_when_aborted, SITUACAO_EDOC_ENVIADA)
        self.assertEqual(state_b_when_aborted, SITUACAO_EDOC_REJEITADA)

    def test_before_hook_returning_false_vetoes_the_transition(self):
        """A falsy _exec_before_* keeps the state and returns False (no error)."""
        with mock.patch.object(
            type(self.doc_a),
            "_exec_before_SITUACAO_EDOC_REJEITADA",
            return_value=False,
        ):
            result = self.doc_a._change_state(SITUACAO_EDOC_REJEITADA)

        self.assertFalse(result)
        self.assertEqual(self.doc_a.state_edoc, SITUACAO_EDOC_A_ENVIAR)

    def test_force_change_skips_the_transition_matrix(self):
        """force_change=True performs a transition WORKFLOW_EDOC does not declare."""
        with self.assertRaises(UserError):
            self.doc_a._change_state(SITUACAO_EDOC_INUTILIZADA)
        self.assertEqual(self.doc_a.state_edoc, SITUACAO_EDOC_A_ENVIAR)

        self.assertTrue(
            self.doc_a._change_state(SITUACAO_EDOC_INUTILIZADA, force_change=True)
        )
        self.assertEqual(self.doc_a.state_edoc, SITUACAO_EDOC_INUTILIZADA)

    def test_avaliable_transition_matrix_for_electronic_documents(self):
        """Freezes the WORKFLOW_EDOC pairs the NF-e lifecycle depends on."""
        allowed = [
            (SITUACAO_EDOC_EM_DIGITACAO, SITUACAO_EDOC_A_ENVIAR),
            (SITUACAO_EDOC_A_ENVIAR, SITUACAO_EDOC_ENVIADA),
            (SITUACAO_EDOC_A_ENVIAR, SITUACAO_EDOC_REJEITADA),
            (SITUACAO_EDOC_A_ENVIAR, SITUACAO_EDOC_AUTORIZADA),
            (SITUACAO_EDOC_A_ENVIAR, SITUACAO_EDOC_DENEGADA),
            (SITUACAO_EDOC_A_ENVIAR, SITUACAO_EDOC_EM_DIGITACAO),
            (SITUACAO_EDOC_ENVIADA, SITUACAO_EDOC_AUTORIZADA),
            (SITUACAO_EDOC_ENVIADA, SITUACAO_EDOC_DENEGADA),
            (SITUACAO_EDOC_REJEITADA, SITUACAO_EDOC_EM_DIGITACAO),
            (SITUACAO_EDOC_REJEITADA, SITUACAO_EDOC_AUTORIZADA),
            (SITUACAO_EDOC_REJEITADA, SITUACAO_EDOC_REJEITADA),
            (SITUACAO_EDOC_AUTORIZADA, SITUACAO_EDOC_CANCELADA),
        ]
        for old_state, new_state in allowed:
            self.assertTrue(
                self.doc_a._avaliable_transition(old_state, new_state),
                f"{old_state} -> {new_state} should be allowed",
            )

        # NOTE: current behavior -- see #4629 discussion. `rejeitada ->
        # enviada` is missing even though a rejected document may legitimately
        # be resent as an asynchronous batch, and `inutilizada` has no
        # incoming transition at all (it is only reachable with
        # force_change=True, which is what the invalidate wizard does).
        refused = [
            (SITUACAO_EDOC_AUTORIZADA, SITUACAO_EDOC_EM_DIGITACAO),
            (SITUACAO_EDOC_REJEITADA, SITUACAO_EDOC_ENVIADA),
            (SITUACAO_EDOC_DENEGADA, SITUACAO_EDOC_EM_DIGITACAO),
            (SITUACAO_EDOC_ENVIADA, SITUACAO_EDOC_CANCELADA),
            (SITUACAO_EDOC_A_ENVIAR, SITUACAO_EDOC_INUTILIZADA),
        ]
        for old_state, new_state in refused:
            self.assertFalse(
                self.doc_a._avaliable_transition(old_state, new_state),
                f"{old_state} -> {new_state} should be refused",
            )
