# Copyright (C) 2026  KMEE INFORMATICA LTDA
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import TransactionCase

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    DOCUMENT_ISSUER_PARTNER,
    SITUACAO_EDOC_A_ENVIAR,
    SITUACAO_EDOC_AUTORIZADA,
    SITUACAO_EDOC_EM_DIGITACAO,
    SITUACAO_EDOC_ENVIADA,
    SITUACAO_EDOC_INUTILIZADA,
    SITUACAO_EDOC_REJEITADA,
    SITUACAO_FISCAL_CANCELADO,
    WORKFLOW_EDOC,
)


class TestLegacyWorkflowCompat(TransactionCase):
    """Regression tests of the legacy workflow compatibility layer.

    Each of these tests fails if the l10n_br_fiscal.document.workflow mixin
    (the bridge between the legacy interface and the state machine engine)
    is removed or bypassed. See models/document_workflow.py.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        cls.fiscal_document = cls.env["l10n_br_fiscal.document"].create(
            {
                "document_type_id": cls.env.ref(
                    "l10n_br_fiscal.document_55_serie_1"
                ).id,
                "fiscal_operation_type": "out",
            }
        )
        cls.fiscal_document.document_electronic = True

    def _confirmed_document(self):
        """A company issued electronic document waiting to be sent."""
        self.fiscal_document.action_document_confirm()
        self.assertEqual(self.fiscal_document.state_edoc, SITUACAO_EDOC_A_ENVIAR)
        return self.fiscal_document

    def _authorized_document(self):
        document = self._confirmed_document()
        document.action_document_send()
        self.assertEqual(document.state_edoc, SITUACAO_EDOC_AUTORIZADA)
        return document

    # -------------------------------------------------------------------------
    # Sending and resending
    # -------------------------------------------------------------------------

    def test_resend_after_rejection(self):
        """A rejected document must be sendable again.

        Regression: without the legacy _action_document_send() filter (and
        the rejeitada -> autorizada transition), a rejected document had no
        way back to the tax authority.
        """
        document = self._confirmed_document()
        document.state_edoc = SITUACAO_EDOC_REJEITADA

        document.action_document_send()

        self.assertEqual(document.state_edoc, SITUACAO_EDOC_AUTORIZADA)

    def test_resend_while_sending(self):
        """Sending a document already in 'enviada' is the receipt query."""
        document = self._confirmed_document()
        document.state_edoc = SITUACAO_EDOC_ENVIADA

        document._action_document_send()

        self.assertEqual(document.state_edoc, SITUACAO_EDOC_AUTORIZADA)

    def test_document_send_keeps_its_legacy_name(self):
        """_document_send() is the public name transmission modules
        override: the engine method must delegate to it."""
        document = self.fiscal_document
        with patch.object(type(document), "_document_send") as legacy_send:
            document._document_send_logic()
        legacy_send.assert_called_once()

    # -------------------------------------------------------------------------
    # Confirmation
    # -------------------------------------------------------------------------

    def test_confirm_non_electronic_numbers_the_document(self):
        """Confirming must stamp the date and the number of the document.

        Regression: confirming through the state machine alone left the
        document without number, serie and date (they are computed by the
        legacy _exec_before_SITUACAO_EDOC_A_ENVIAR).
        """
        document = self.env.ref("l10n_br_fiscal.demo_nfe_same_state")
        document.write(
            {
                "document_electronic": False,
                "document_number": False,
                "document_date": False,
                "date_in_out": False,
            }
        )

        document.action_document_confirm()

        self.assertEqual(document.state_edoc, SITUACAO_EDOC_A_ENVIAR)
        self.assertTrue(document.document_number)
        self.assertEqual(document.document_serie, document.document_serie_id.code)
        self.assertTrue(document.document_date)
        self.assertTrue(document.date_in_out)

    def test_confirm_partner_issued_document(self):
        """A partner issued document is authorized on confirmation: there is
        nothing for us to transmit."""
        document = self.fiscal_document
        document.issuer = DOCUMENT_ISSUER_PARTNER

        document.action_document_confirm()

        self.assertEqual(document.state_edoc, SITUACAO_EDOC_AUTORIZADA)
        self.assertTrue(document.document_date)

    # -------------------------------------------------------------------------
    # Legacy hooks dispatching
    # -------------------------------------------------------------------------

    def test_legacy_before_hook_vetoes_transition(self):
        """A third party module returning False in a legacy _exec_before_*
        hook must still veto the transition (this is how the NFS-e providers
        abort a cancellation the city hall refused)."""
        document = self._authorized_document()

        with patch.object(
            type(document),
            "_exec_before_SITUACAO_EDOC_CANCELADA",
            return_value=False,
        ) as before_hook:
            document._document_cancel("Cancelamento de teste")

        before_hook.assert_called_once()
        self.assertEqual(document.state_edoc, SITUACAO_EDOC_AUTORIZADA)

    def test_legacy_after_hook_called_on_authorization(self):
        """A third party module override of a legacy _exec_after_* hook must
        still be called (this is how l10n_br_nfe generates the DANFE)."""
        document = self._confirmed_document()

        with patch.object(
            type(document), "_exec_after_SITUACAO_EDOC_AUTORIZADA"
        ) as after_hook:
            document.action_document_send()

        after_hook.assert_called_once()
        self.assertEqual(document.state_edoc, SITUACAO_EDOC_AUTORIZADA)

    def test_new_trigger_dispatches_legacy_hooks(self):
        """The new API entry point must go through the legacy dispatchers
        too, otherwise a module migrated to the new API would silently stop
        calling the overrides of the modules that were not migrated yet."""
        document = self._confirmed_document()

        with patch.object(
            type(document), "_before_change_state", return_value=True
        ) as before_dispatcher, patch.object(
            type(document), "_after_change_state"
        ) as after_dispatcher:
            document._trigger_fsm("action_authorize")

        before_dispatcher.assert_called_once_with(
            SITUACAO_EDOC_A_ENVIAR, SITUACAO_EDOC_AUTORIZADA
        )
        after_dispatcher.assert_called_once_with(
            SITUACAO_EDOC_A_ENVIAR, SITUACAO_EDOC_AUTORIZADA
        )
        self.assertEqual(document.state_edoc, SITUACAO_EDOC_AUTORIZADA)

    def test_back2draft_sped_guard(self):
        """A document whose fiscal state is considered cancelled by SPED
        cannot go back to draft."""
        document = self._confirmed_document()
        document.state_fiscal = SITUACAO_FISCAL_CANCELADO

        with self.assertRaises(UserError):
            document.action_document_back2draft()

    # -------------------------------------------------------------------------
    # State machine engine
    # -------------------------------------------------------------------------

    def test_change_state_multi_record(self):
        """_change_state() must keep working on a multi record recordset
        (l10n_br_cte and the account move workflow rely on it)."""
        documents = self.fiscal_document | self.fiscal_document.copy()

        self.assertTrue(documents._change_state(SITUACAO_EDOC_A_ENVIAR))

        self.assertEqual(set(documents.mapped("state_edoc")), {SITUACAO_EDOC_A_ENVIAR})

    def test_no_spurious_write_without_transition(self):
        """Neither building the state machine nor a refused/vetoed
        transition may write state_edoc in the database."""
        document = self._authorized_document()
        document_class = type(document)
        original_write = document_class.write
        written_states = []

        def counting_write(records, vals):
            if "state_edoc" in vals:
                written_states.append(vals["state_edoc"])
            return original_write(records, vals)

        with patch.object(document_class, "write", counting_write):
            # merely building the machine must not write anything
            document.get_state_machine_config()

            # a transition the machine refuses must not write anything
            with self.assertRaises(UserError):
                document._trigger_fsm("action_validate")

            # a transition vetoed by a legacy hook must not write anything
            # either, and the veto is reported to the caller instead of
            # passing for a successful transition
            with patch.object(
                document_class,
                "_exec_before_SITUACAO_EDOC_CANCELADA",
                return_value=False,
            ):
                with self.assertRaises(UserError):
                    document._trigger_fsm("action_cancel_fsm")

        self.assertEqual(written_states, [])
        self.assertEqual(document.state_edoc, SITUACAO_EDOC_AUTORIZADA)

    def test_state_machine_contains_every_legacy_transition(self):
        """The FSM table must be a superset of the legacy tuples.

        Confronting the two tables is the point: asserting that WORKFLOW_EDOC
        allows what WORKFLOW_EDOC allows would be a tautology and would not
        notice a source dropped from the machine.
        """
        document = self.fiscal_document
        fsm_edges = document._fsm_allowed_transitions()
        missing = [
            (old_state, new_state)
            for old_state, new_state in WORKFLOW_EDOC
            if (old_state, new_state) not in fsm_edges
        ]
        self.assertFalse(
            missing,
            f"the state machine dropped legacy transitions: {missing}",
        )

    def test_legacy_api_stays_narrower_than_the_machine(self):
        """The legacy validation must never accept what the machine refuses.

        The machine is a superset on purpose (resending a rejected document,
        for instance). The dangerous direction is the other one: a legacy
        caller getting through an edge the machine does not declare.
        """
        document = self.fiscal_document
        fsm_edges = document._fsm_allowed_transitions()
        wider = [
            (old_state, new_state)
            for old_state, new_state in WORKFLOW_EDOC
            if (old_state, new_state) not in fsm_edges
        ]
        self.assertFalse(wider, f"legacy API is wider than the machine: {wider}")
        self.assertFalse(
            document._avaliable_transition(
                SITUACAO_EDOC_INUTILIZADA, SITUACAO_EDOC_EM_DIGITACAO
            )
        )

    def test_third_party_state_is_not_a_silent_noop(self):
        """A state added by another module must be reachable.

        The compatibility layer dispatches the legacy hooks with an if/elif
        chain over the eight known states. A state added by a municipal NFS-e
        provider has no branch of its own, so the default of the dispatch has
        to be "allow", otherwise extending the machine, which is what the
        USAGE of this module documents, writes nothing and raises nothing.
        """
        document = self.fiscal_document
        document.write({"state_edoc": SITUACAO_EDOC_A_ENVIAR})

        self.assertTrue(
            document._before_change_state(SITUACAO_EDOC_A_ENVIAR, "em_processamento"),
            "the dispatch of an unknown state must default to allowing it",
        )

    def test_vetoed_trigger_raises_instead_of_returning(self):
        """_trigger_fsm must not swallow a veto.

        A legacy hook returning a falsy value stops the write. The new API
        cannot report that as a success: the caller has no other way of
        telling a refusal from a transition that happened.
        """
        document = self._confirmed_document()
        document_class = type(document)

        with patch.object(
            document_class,
            "_exec_before_SITUACAO_EDOC_ENVIADA",
            lambda self, old_state, new_state: False,
        ):
            with self.assertRaises(UserError):
                document._trigger_fsm("action_send")

        self.assertEqual(document.state_edoc, SITUACAO_EDOC_A_ENVIAR)
