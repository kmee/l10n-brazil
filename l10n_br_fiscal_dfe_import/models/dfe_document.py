# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class L10nBrFiscalDfeDocument(models.Model):
    _name = "l10n_br_fiscal_dfe.document"
    _inherit = [
        "l10n_br_fiscal_dfe.document",
        "mail.thread",
        "mail.activity.mixin",
    ]

    import_requested_user_id = fields.Many2one(
        comodel_name="res.users",
        string="Import Requested By",
        help="User that asked to import this access key. The fiscal document "
        "is created when the complete XML arrives.",
    )

    def _dfe_import_request(self):
        """Register the acknowledgement (ciência) so the complete XML is
        released, and import it when it arrives."""
        self.ensure_one()
        self.sudo().import_requested_user_id = self.env.user
        if self.manifestation_status != "sem_manifestacao":
            return
        event = self.env["l10n_br_nfe.md_event"].create(
            {
                "access_key": self.access_key,
                "event_type": "ciente",
                "company_id": self.company_id.id,
                "document_type": "nfe",
                "dfe_document_id": self.id,
            }
        )
        event.with_company(self.company_id).action_confirm()

    def _dfe_import_requested_xml(self):
        """Create the fiscal document of an import asked by access key."""
        self.ensure_one()
        user = self.import_requested_user_id
        self = self.with_context(lang=user.lang)
        complete = self._get_complete_dfe()
        if not user or not complete.attachment_id:
            return
        self.sudo().import_requested_user_id = False
        documents, errors = (
            self.env["l10n_br_fiscal.document"]
            .with_user(user)
            .dfe_import_files(
                [
                    (
                        complete.attachment_id.name,
                        complete.attachment_id.raw,
                    )
                ]
            )
        )
        for document in documents:
            document.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=user.id,
                note=_("Document created from the access key %s.") % self.access_key,
            )
        for _name, message in errors:
            self.company_id._dfe_log(message, log_type="error", fiscal_type="nfe")
        if errors:
            self.sudo().activity_schedule(
                "mail.mail_activity_data_warning",
                user_id=user.id,
                summary=_("The NF-e could not be imported"),
                note="\n".join(message for _name, message in errors),
            )
