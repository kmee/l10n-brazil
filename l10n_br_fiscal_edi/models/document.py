# Copyright (C) 2019  Renato Lima - Akretion
# Copyright (C) 2019  KMEE INFORMATICA LTDA
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from transitions import Machine, MachineError

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    DOCUMENT_ISSUER,
    DOCUMENT_ISSUER_COMPANY,
    DOCUMENT_STATE_CANCEL,
    DOCUMENT_STATE_DRAFT,
    DOCUMENT_STATE_OPEN,
    PROCESSADOR_NENHUM,
)

from ..constants.fiscal import (
    DOCUMENT_STATE_AUTHORIZED,
    DOCUMENT_STATE_DENIED,
    DOCUMENT_STATE_REJECTED,
    DOCUMENT_STATE_SENDING,
)


def filter_processador(record):
    if record.document_electronic and record.processador_edoc == PROCESSADOR_NENHUM:
        return True
    return False


class FiscalDocumentStateProxy:
    """Plain Python model the `transitions` Machine is bound to.

    The Machine assigns the initial state to its model when it is built
    (`transitions` calls set_state() from add_model), so binding it directly
    to an Odoo record would write state_edoc in the database on every
    instantiation, even when no transition happens at all. The Machine only
    moves this proxy around: the single real write is done by
    _change_state(), and only when the transition is actually accepted.
    """

    def __init__(self, state_edoc):
        self.state_edoc = state_edoc


class Document(models.Model):
    """
    Fiscal Document EDI extension implementing State Machine workflow.

    The l10n_br_fiscal.document.workflow mixin is the compatibility layer
    keeping the legacy interface (_exec_before_*/_exec_after_*,
    _change_state, _document_confirm...) working on top of this engine. See
    models/document_workflow.py.
    """

    _name = "l10n_br_fiscal.document"

    _inherit = [
        "l10n_br_fiscal.document",
        "l10n_br_fiscal.document.workflow",
    ]

    event_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.event",
        inverse_name="document_id",
        string="Events",
        copy=False,
        readonly=True,
    )

    correction_event_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.event",
        inverse_name="document_id",
        domain=[("type", "=", "14")],
        string="Correction Events",
        copy=False,
        readonly=True,
    )

    issuer = fields.Selection(
        selection=DOCUMENT_ISSUER,
        default=DOCUMENT_ISSUER_COMPANY,
    )

    status_code = fields.Char(
        copy=False,
    )

    status_name = fields.Char(
        copy=False,
    )

    status_description = fields.Char(
        compute="_compute_status_description",
        copy=False,
    )

    # Authorization Event Related Fields
    authorization_event_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.event",
        string="Authorization Event",
        readonly=True,
        copy=False,
    )

    authorization_date = fields.Datetime(
        related="authorization_event_id.protocol_date",
        string="Authorization Protocol Date",
    )

    authorization_protocol = fields.Char(
        related="authorization_event_id.protocol_number",
        string="Authorization Protocol Number",
    )

    send_file_id = fields.Many2one(
        comodel_name="ir.attachment",
        related="authorization_event_id.file_request_id",
        string="Send Document File XML",
        ondelete="restrict",
        readonly=True,
    )

    authorization_file_id = fields.Many2one(
        comodel_name="ir.attachment",
        related="authorization_event_id.file_response_id",
        string="Authorization File XML",
        ondelete="restrict",
        readonly=True,
    )

    # Cancel Event Related Fields
    cancel_event_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.event",
        string="Cancel Event",
        copy=False,
    )

    cancel_date = fields.Datetime(
        related="cancel_event_id.protocol_date",
        string="Cancel Protocol Date",
    )

    cancel_protocol_number = fields.Char(
        related="cancel_event_id.protocol_number",
        string="Cancel Protocol Protocol",
    )

    cancel_file_id = fields.Many2one(
        comodel_name="ir.attachment",
        related="cancel_event_id.file_response_id",
        string="Cancel File XML",
        ondelete="restrict",
        readonly=True,
    )

    # Invalidate Event Related Fields
    invalidate_event_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.event",
        string="Invalidate Event",
        copy=False,
    )

    invalidate_date = fields.Datetime(
        related="invalidate_event_id.protocol_date",
        string="Invalidate Protocol Date",
    )

    invalidate_protocol_number = fields.Char(
        related="invalidate_event_id.protocol_number",
        string="Invalidate Protocol Number",
    )

    invalidate_file_id = fields.Many2one(
        comodel_name="ir.attachment",
        related="invalidate_event_id.file_response_id",
        string="Invalidate File XML",
        ondelete="restrict",
        readonly=True,
    )

    document_version = fields.Char(string="Version", default="4.00", readonly=True)

    is_edoc_printed = fields.Boolean(string="Is Printed?", readonly=True)

    file_report_id = fields.Many2one(
        comodel_name="ir.attachment",
        string="Document Report",
        ondelete="restrict",
        readonly=True,
        copy=False,
    )

    @api.depends("status_code", "status_name")
    def _compute_status_description(self):
        for record in self:
            if record.status_code:
                record.status_description = "{} - {}".format(
                    record.status_code or "",
                    record.status_name or "",
                )
            else:
                record.status_description = False

    @api.constrains("issuer")
    def _check_issuer(self):
        for record in self.filtered(lambda d: d.document_electronic):
            if not record.issuer:
                raise ValidationError(
                    _(
                        "The field 'Issuer' is required for brazilian electronic "
                        "documents!"
                    )
                )

    # -------------------------------------------------------------------------
    # State Machine Logic
    # -------------------------------------------------------------------------

    def _fsm_states(self):
        """The machine states are the state_edoc values.

        They are read from the field selection (instead of a hardcoded list)
        so modules adding their own state_edoc value get a machine that knows
        it: `transitions` raises ValueError ("State '%s' is not a registered
        state.") as soon as a transition points to a state the machine does
        not know, which is exactly what a module extending this table with
        its own state does.
        """
        selection = self._fields["state_edoc"].selection
        if callable(selection):
            selection = selection(self)
        return [state for state, _label in selection]

    def get_state_machine_config(self):
        """Declarative definition of the fiscal document state machine.

        The transitions are the source of truth of the new API: every
        _trigger_fsm() call is validated against them.

        The legacy _avaliable_transition() keeps validating against the
        WORKFLOW_EDOC tuples, which are a strict subset of this table: the
        machine was built from them and then extended with the edges the
        refactor adds on purpose (resending a rejected document, for
        instance). So a transition refused by the legacy API may be accepted
        by the new one, never the opposite, and test_legacy_workflow_compat
        asserts that containment. Deriving the legacy validation from this
        table would silently widen the legacy API, which is why it is not
        done here.
        """
        self.ensure_one()
        return {
            "states": self._fsm_states(),
            "transitions": [
                # Validate: Draft -> Open
                {
                    "trigger": "action_validate",
                    "source": DOCUMENT_STATE_DRAFT,
                    "dest": DOCUMENT_STATE_OPEN,
                    "before": "_before_document_validate",
                },
                # Send: Open -> Sending
                {
                    "trigger": "action_send",
                    "source": [
                        DOCUMENT_STATE_DRAFT,
                        DOCUMENT_STATE_OPEN,
                        DOCUMENT_STATE_REJECTED,
                    ],
                    "dest": DOCUMENT_STATE_SENDING,
                    "before": "_before_document_send",
                    "after": "_after_document_send",
                },
                # Authorize: Sending -> Authorized
                {
                    "trigger": "action_authorize",
                    "source": [
                        DOCUMENT_STATE_SENDING,
                        DOCUMENT_STATE_OPEN,
                        # A rejected document can be sent again and a
                        # partner issued document is authorized straight
                        # from the draft state.
                        DOCUMENT_STATE_REJECTED,
                        DOCUMENT_STATE_DRAFT,
                    ],
                    "dest": DOCUMENT_STATE_AUTHORIZED,
                    "after": "_after_document_authorize",
                },
                # Reject: Sending -> Rejected
                {
                    "trigger": "action_reject",
                    "source": [
                        DOCUMENT_STATE_SENDING,
                        DOCUMENT_STATE_OPEN,
                        DOCUMENT_STATE_DRAFT,
                        # A new submission of a rejected document can be
                        # rejected again.
                        DOCUMENT_STATE_REJECTED,
                    ],
                    "dest": DOCUMENT_STATE_REJECTED,
                },
                # Deny: Sending -> Denied
                {
                    "trigger": "action_deny",
                    "source": [
                        DOCUMENT_STATE_SENDING,
                        DOCUMENT_STATE_OPEN,
                        DOCUMENT_STATE_DRAFT,
                    ],
                    "dest": DOCUMENT_STATE_DENIED,
                    "after": "_after_document_deny",
                },
                # Synchronization with the tax authority. A consultation
                # such as `nfeConsultaNF` reads the document straight from the
                # SEFAZ database, so its answer is authoritative and overrides
                # the local state from wherever it is: the document may be
                # locally cancelled and authorized at SEFAZ. These edges are
                # declared instead of being written raw so the callbacks of
                # the destination still run, which is what generates the DANFE
                # of a document rescued into `autorizada`. Only an
                # authoritative answer of the tax authority may fire them.
                {
                    "trigger": "action_sync_authorized",
                    "source": "*",
                    "dest": DOCUMENT_STATE_AUTHORIZED,
                    "after": "_after_document_authorize",
                },
                {
                    "trigger": "action_sync_cancelled",
                    "source": "*",
                    "dest": DOCUMENT_STATE_CANCEL,
                },
                {
                    "trigger": "action_sync_denied",
                    "source": "*",
                    "dest": DOCUMENT_STATE_DENIED,
                    "after": "_after_document_deny",
                },
                {
                    "trigger": "action_sync_rejected",
                    "source": "*",
                    "dest": DOCUMENT_STATE_REJECTED,
                },
                # Cancel: Authorized -> Cancel
                {
                    "trigger": "action_cancel_fsm",
                    "source": [
                        DOCUMENT_STATE_AUTHORIZED,
                        DOCUMENT_STATE_OPEN,  # Allow canceling if manual/not sent
                        DOCUMENT_STATE_REJECTED,
                        DOCUMENT_STATE_DRAFT,
                        DOCUMENT_STATE_SENDING,
                    ],
                    "dest": DOCUMENT_STATE_CANCEL,
                    "before": "_before_document_cancel",
                },
                # Back to Draft
                {
                    "trigger": "action_draft_fsm",
                    "source": [
                        DOCUMENT_STATE_OPEN,
                        DOCUMENT_STATE_SENDING,
                        DOCUMENT_STATE_REJECTED,
                        DOCUMENT_STATE_CANCEL,
                        DOCUMENT_STATE_DENIED,
                        DOCUMENT_STATE_DRAFT,
                    ],
                    "dest": DOCUMENT_STATE_DRAFT,
                    "before": "_before_document_back2draft",
                },
            ],
            "initial": self.state_edoc,
        }

    def _fsm_transition_sources(self, transition):
        """The source states of a transition, wildcard expanded.

        `transitions` accepts "*" as "from any state", which the machine uses
        for the synchronization with the tax authority.
        """
        self.ensure_one()
        source = transition["source"]
        if source == "*":
            return self._fsm_states()
        if isinstance(source, str):
            return [source]
        return source

    def _fsm_allowed_transitions(self):
        """The set of (source, dest) state_edoc pairs the machine allows."""
        self.ensure_one()
        allowed = set()
        for transition in self.get_state_machine_config()["transitions"]:
            for state in self._fsm_transition_sources(transition):
                allowed.add((state, transition["dest"]))
        return allowed

    def _fsm_transition_callbacks(self, old_state, new_state, kind):
        """Return the `before`/`after` callbacks declared by the machine for
        the (old_state, new_state) edge."""
        self.ensure_one()
        callbacks = []
        for transition in self.get_state_machine_config()["transitions"]:
            if (
                old_state not in self._fsm_transition_sources(transition)
                or transition["dest"] != new_state
            ):
                continue
            names = transition.get(kind) or []
            if isinstance(names, str):
                names = [names]
            for name in names:
                if name not in callbacks:
                    callbacks.append(name)
        return callbacks

    def _run_fsm_callbacks(self, old_state, new_state, kind):
        """Run the machine callbacks of a transition against the record.

        They are executed by _change_state() (through
        _before_change_state/_after_change_state), and not by the
        `transitions` Machine itself, so that the legacy hooks and the new
        callbacks are called at the very same point of the flow, whatever
        the entry point (legacy _change_state or new _trigger_fsm).
        """
        self.ensure_one()
        for callback in self._fsm_transition_callbacks(old_state, new_state, kind):
            getattr(self, callback)()

    def _trigger_fsm(self, trigger):
        """Fire a state machine trigger for each record of the recordset."""
        for doc in self:
            config = doc.get_state_machine_config()
            proxy = FiscalDocumentStateProxy(config["initial"])
            Machine(
                model=proxy,
                states=config["states"],
                # The Odoo callbacks are run by _change_state(), against the
                # record and not against the proxy.
                transitions=[
                    {
                        key: value
                        for key, value in transition.items()
                        if key in ("trigger", "source", "dest")
                    }
                    for transition in config["transitions"]
                ],
                initial=config["initial"],
                model_attribute="state_edoc",  # Bind to state_edoc
                auto_transitions=False,
                ignore_invalid_triggers=False,
            )
            try:
                getattr(proxy, trigger)()
            except (AttributeError, MachineError) as e:
                raise UserError(
                    _("State transition failed for action '%(action)s': %(error)s")
                    % {"action": trigger, "error": e}
                ) from e
            # The Machine above already validated the edge against the FSM
            # table (the single source of truth for the new API), which is a
            # superset of the legacy tuples. force_change=True skips only the
            # redundant legacy re-validation in _change_state(); every
            # before/after hook still runs.
            if not doc._change_state(proxy.state_edoc, force_change=True):
                # A legacy _exec_before_* hook vetoed the transition by
                # returning a falsy value. The new API has no silent veto: the
                # caller must be able to tell a refusal from a success.
                raise UserError(
                    _(
                        "The transition '%(action)s' of the document "
                        "%(document)s was refused.",
                        action=trigger,
                        document=doc.display_name,
                    )
                )

    def _get_state_to_action_map(self):
        return {
            DOCUMENT_STATE_OPEN: "action_validate",
            DOCUMENT_STATE_SENDING: "action_send",
            DOCUMENT_STATE_AUTHORIZED: "action_authorize",
            DOCUMENT_STATE_REJECTED: "action_reject",
            DOCUMENT_STATE_DENIED: "action_deny",
            DOCUMENT_STATE_CANCEL: "action_cancel_fsm",
            DOCUMENT_STATE_DRAFT: "action_draft_fsm",
        }

    def _get_state_to_sync_action_map(self):
        """Triggers that apply an authoritative answer of the tax authority.

        They accept any source state on purpose: what they express is not a
        business transition but the local state being corrected to match what
        the tax authority holds.
        """
        return {
            DOCUMENT_STATE_AUTHORIZED: "action_sync_authorized",
            DOCUMENT_STATE_CANCEL: "action_sync_cancelled",
            DOCUMENT_STATE_DENIED: "action_sync_denied",
            DOCUMENT_STATE_REJECTED: "action_sync_rejected",
        }

    # -------------------------------------------------------------------------
    # Transition Callbacks
    # -------------------------------------------------------------------------
    # These hooks are the new API. While the compatibility layer is in place
    # their default implementation is empty: the default behavior lives in
    # the legacy _exec_before_*/_exec_after_* hooks of the
    # l10n_br_fiscal.document.workflow mixin, which is called at the same
    # point of the flow. Once the mixin is removed, the default behavior
    # moves here.

    def _before_document_validate(self):
        """Called before draft -> open. See
        _exec_before_SITUACAO_EDOC_A_ENVIAR (document date, numbering,
        comments, checks and export)."""

    def _before_document_send(self):
        """Called before open -> sending. See
        _exec_before_SITUACAO_EDOC_ENVIADA."""

    def _after_document_send(self):
        """Called after open -> sending. See
        _exec_after_SITUACAO_EDOC_ENVIADA.

        Note it does NOT transmit the document: the transmission is driven
        by action_document_send()/_document_send(), and providers do reach
        the 'sending' state from within the transmission itself (a
        transmission here would recurse).
        """

    def _after_document_authorize(self):
        """Called after the document is authorized. See
        _exec_after_SITUACAO_EDOC_AUTORIZADA (l10n_br_nfe generates the
        DANFE there)."""

    def _after_document_deny(self):
        """Called after the document is denied. See
        _exec_after_SITUACAO_EDOC_DENEGADA / exec_after_SITUACAO_EDOC_DENEGADA
        (l10n_br_account cancels the related account moves there)."""

    def _before_document_cancel(self):
        """Called before the document is cancelled. See
        _exec_before_SITUACAO_EDOC_CANCELADA (the NFS-e providers do call
        the web service there and veto the transition when it fails)."""

    def _before_document_back2draft(self):
        """Called before the document goes back to draft. See
        document_back2draft()."""
        self.xml_error_message = False
        self.file_report_id = False

    # -------------------------------------------------------------------------
    # Logic Implementation
    # -------------------------------------------------------------------------

    def _copy_operation_comments(self):
        """Copy the default comments of the fiscal operation to the document
        and its lines, so _document_comment() can render them."""
        for record in self:
            if not record.comment_ids and record.fiscal_operation_id.comment_ids:
                record.comment_ids |= record.fiscal_operation_id.comment_ids
            for line in record.fiscal_line_ids:
                if not line.comment_ids and line.fiscal_operation_line_id.comment_ids:
                    line.comment_ids |= line.fiscal_operation_line_id.comment_ids

    def _document_send(self):
        """
        Logic to handle document sending.
        Separates electronic vs non-electronic handling.
        """
        no_electronic = self.filtered(
            lambda d: not d.document_electronic
            or not d.issuer == DOCUMENT_ISSUER_COMPANY
        )
        # Non-electronic/partner-issued docs go straight to Authorized:
        # there is nothing to transmit.
        no_electronic._no_eletronic_document_send()
        electronic = self - no_electronic
        electronic._eletronic_document_send()

    def _document_send_logic(self):
        """Deprecated alias of the legacy _document_send()."""
        return self._document_send()

    def _eletronic_document_send(self):
        """Implement this method in your transmission module,
        to send the electronic document and use the method _change_state
        to update the state of the transmited document,

        def _eletronic_document_send(self):
            super()._document_send()
            for record in self.filtered(myfilter):
                Do your transmission stuff
                [...]
                Change the state of the document
        """
        for record in self.filtered(filter_processador):
            record._change_state(DOCUMENT_STATE_AUTHORIZED)

    def _document_status(self):
        """Retorna o status do documento em texto e se necessário,
        atualiza o status do documento"""
        return

    def serialize(self):
        """
        Serialize the document to a list of EDocs (objects from erpbrasil.edoc).
        Modules should override _serialize to add their EDocs.
        """
        edocs = []
        self._serialize(edocs)
        return edocs

    def _serialize(self, edocs):
        """
        Hook for modules to add their serialized EDocs to the list.
        """
        return edocs

    # -------------------------------------------------------------------------
    # Actions / Buttons
    # -------------------------------------------------------------------------
    # these workflow methods are plugged here so their interface defined in
    # l10n_br_fiscal can easily be overriden in other modules.

    def action_document_confirm(self):
        super().action_document_confirm()
        return self._document_confirm_to_send()

    def action_document_send(self):
        super().action_document_send()
        return self._action_document_send()

    def action_document_back2draft(self):
        super().action_document_back2draft()
        return self._action_document_back2draft()

    def action_document_cancel(self):
        super().action_document_cancel()
        return self._action_document_cancel()

    def action_document_invalidate(self):
        super().action_document_invalidate()
        return self._action_document_invalidate()

    def action_document_correction(self):
        super().action_document_correction()
        return self._action_document_correction()

    def exec_after_SITUACAO_EDOC_DENEGADA(self, old_state, new_state):
        # see https://github.com/OCA/l10n-brazil/pull/3272
        super().exec_after_SITUACAO_EDOC_DENEGADA(old_state, new_state)
        return self._exec_after_SITUACAO_EDOC_DENEGADA(old_state, new_state)

    # -------------------------------------------------------------------------
    # Misc Tools
    # -------------------------------------------------------------------------

    def _target_new_tab(self, attachment_id):
        if attachment_id:
            return {
                "type": "ir.actions.act_url",
                "url": f"/web/content/{attachment_id.id}/{attachment_id.name}",
                "target": "new",
            }

    def view_xml(self):
        self.ensure_one()
        super().view_xml()
        xml_file = self.authorization_file_id or self.send_file_id
        if not xml_file:
            self._document_export()
            xml_file = self.authorization_file_id or self.send_file_id
        if not xml_file:
            raise UserError(_("No XML file generated!"))
        return self._target_new_tab(xml_file)

    def make_pdf(self):
        pass

    def view_pdf(self):
        self.ensure_one()
        super().view_pdf()
        if not self.file_report_id or not self.authorization_file_id:
            self.make_pdf()
        if not self.file_report_id:
            raise UserError(_("No PDF file generated!"))
        return self._target_new_tab(self.file_report_id)
