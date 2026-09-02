# Copyright (C) 2019  Renato Lima - Akretion
# Copyright (C) 2019  KMEE INFORMATICA LTDA
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    DOCUMENT_ISSUER,
    DOCUMENT_ISSUER_COMPANY,
    PROCESSADOR_NENHUM,
    SITUACAO_EDOC_AUTORIZADA,
)


def filter_processador(record):
    if record.document_electronic and record.processador_edoc == PROCESSADOR_NENHUM:
        return True
    return False


class Document(models.Model):
    """
    As of August 2024, this is the extraction of the legacy
    l10n_br_fiscal.document.electronic mixin that was part of l10n_br_fiscal
    from version 12 to 14. This code was made before the OCA/edi and OCA/edi-framework
    and might easily be improved...
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
            record._change_state(SITUACAO_EDOC_AUTORIZADA)

    def _document_send(self):
        no_electronic = self.filtered(
            lambda d: not d.document_electronic
            or not d.issuer == DOCUMENT_ISSUER_COMPANY
        )
        no_electronic._no_eletronic_document_send()
        electronic = self - no_electronic
        electronic._eletronic_document_send()

    def serialize(self):
        edocs = []
        self._serialize(edocs)
        return edocs

    def _serialize(self, edocs):
        return edocs

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

    def _download_url(self, attachment):
        return f"/web/content/{attachment.id}/{attachment.name}?download=true"

    def _xml_attachment(self):
        """The authorized XML, and the sent one while authorization has not come."""
        self.ensure_one()
        return self.authorization_file_id or self.send_file_id

    def _report_attachment(self):
        self.ensure_one()
        if not self.file_report_id:
            self.make_pdf()
        return self.file_report_id

    def _collect_download_files(self, xml=True, report=True):
        """Files to hand to the browser, and the documents left without any.

        A document still in typing has nothing to give, and a selection of many
        notes usually mixes those with the authorized ones. Refusing the whole
        batch because of one of them is worse than handing over what exists and
        naming what was left out, so the ones without a file come back apart
        instead of raising.
        """
        files = []
        skipped = self.browse()
        for record in self:
            attachments = self.env["ir.attachment"]
            if xml:
                attachments |= record._xml_attachment()
            if report:
                attachments |= record._report_attachment()
            if not attachments:
                skipped |= record
                continue
            files.extend(
                {"url": record._download_url(each), "name": each.name}
                for each in attachments
            )
        return files, skipped

    def action_download_files(self, xml=True, report=True):
        """Hand the files over one by one, unzipped.

        A download of the browser carries one file, so who walks the list is the
        client: the action below receives the addresses and asks for one at a
        time. From three files on the browser asks the person once whether to
        accept several, which is the price of not zipping.
        """
        files, skipped = self._collect_download_files(xml=xml, report=report)
        if not files:
            raise UserError(
                _(
                    "None of the selected documents has a file to download. A "
                    "document still in typing has no XML and no report yet."
                )
            )
        return {
            "type": "ir.actions.client",
            "tag": "l10n_br_fiscal_edi.download_files",
            "params": {
                "files": files,
                "skipped": skipped.mapped("display_name"),
            },
        }

    def action_download_xml(self):
        return self.action_download_files(report=False)

    def action_download_report(self):
        return self.action_download_files(xml=False)

    def action_download_xml_and_report(self):
        return self.action_download_files()

    def view_pdf(self):
        self.ensure_one()
        super().view_pdf()
        if not self.file_report_id or not self.authorization_file_id:
            self.make_pdf()
        if not self.file_report_id:
            raise UserError(_("No PDF file generated!"))
        return self._target_new_tab(self.file_report_id)

    def _document_status(self):
        """Retorna o status do documento em texto e se necessário,
        atualiza o status do documento"""
        return

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
