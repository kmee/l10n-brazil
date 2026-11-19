# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# the acknowledgement (ciência) is only accepted until 10 days after the
# authorization (Ajuste SINIEF 07/05, cláusula décima quinta-C, par. 4)
ACKNOWLEDGEMENT_DAYS = 10


class DocumentImportDfeWizard(models.TransientModel):
    _name = "l10n_br_fiscal_dfe_import.wizard"
    _description = "Import Fiscal Document by File or Access Key"

    access_key = fields.Char(
        help="Access key of an NF-e issued to the current company.",
    )

    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        string="Files",
        help="One XML file, several, or a zip with them.",
    )

    state = fields.Selection(
        selection=[("draft", "Draft"), ("confirm", "Confirm")],
        default="draft",
    )

    confirm_message = fields.Text(readonly=True)

    dfe_document_id = fields.Many2one(
        comodel_name="l10n_br_fiscal_dfe.document",
        readonly=True,
    )

    def action_import(self):
        self.ensure_one()
        access_key = self.env["dfe.specific.search.wizard"]._sanitize_access_key(
            self.access_key
        )
        if access_key and self.attachment_ids:
            raise UserError(_("Inform the access key or upload files, not both."))
        if access_key:
            return self._import_access_key(access_key)
        if not self.attachment_ids:
            raise UserError(_("Inform the access key or upload at least one file."))
        return self._import_files(
            [(attachment.name, attachment.raw) for attachment in self.attachment_ids]
        )

    def action_confirm_acknowledgement(self):
        self.ensure_one()
        self.dfe_document_id._dfe_import_request()
        return self._notification(
            _("Acknowledgement registered"),
            _(
                "The fiscal document will be created when the complete XML "
                "arrives from the distribution service."
            ),
            "info",
        )

    def _import_files(self, files, dfe_document=None):
        warnings = []
        documents, errors = self.env["l10n_br_fiscal.document"].dfe_import_files(
            files, warnings=warnings
        )
        if dfe_document:
            for document in documents.filtered(
                lambda doc: not any(
                    dfe_document.access_key in (msg.body or "")
                    for msg in doc.message_ids
                )
            ):
                document.message_post(
                    body=_("Document created from the access key %s.")
                    % dfe_document.access_key
                )
                dfe_document.sudo().message_post(
                    body=_("Fiscal document %s created.") % document.display_name
                )
        messages = "\n".join(f"{name}: {message}" for name, message in errors)
        if not documents:
            raise UserError(_("No file was imported:\n%s") % messages)
        self.attachment_ids.filtered(lambda att: att.res_model == self._name).unlink()
        action = self._documents_action(documents)
        if errors:
            return self._notification(
                _("Some files were not imported"),
                "\n".join([messages] + [f"{n}: {m}" for n, m in warnings]),
                "warning",
                sticky=True,
                action=action,
            )
        if warnings:
            return self._notification(
                _("Note already imported"),
                "\n".join(f"{name}: {message}" for name, message in warnings),
                "info",
                sticky=True,
                action=action,
            )
        return action

    def _import_access_key(self, access_key):
        Wizard = self.env["dfe.specific.search.wizard"]
        Wizard._validate_access_key(access_key)
        if access_key[20:22] != "55":
            raise UserError(_("Only NF-e (model 55) can be imported by access key."))
        company = self.env.company
        existing = self.env["l10n_br_fiscal.document"].search(
            [("document_key", "=", access_key), ("company_id", "=", company.id)],
            limit=1,
        )
        if existing:
            return self._notification(
                _("Note already imported"),
                _("This note was already imported; the existing document was opened."),
                "info",
                sticky=True,
                action=self._documents_action(existing),
            )
        dfe_document = self._find_dfe_document(access_key, company)
        if not dfe_document:
            self._search_distribution(company, access_key)
            dfe_document = self._find_dfe_document(access_key, company)
        if not dfe_document:
            raise UserError(
                _(
                    "The NF-e was not found in the distribution service. Upload "
                    "its XML file instead."
                )
            )
        if dfe_document.document_state in ("2", "3"):
            raise UserError(_("This NF-e was cancelled or denied."))
        complete = dfe_document._get_complete_dfe()
        if complete.attachment_id:
            attachment = complete.attachment_id
            return self._import_files(
                [(attachment.name, attachment.raw)], dfe_document=dfe_document
            )
        return self._ask_acknowledgement(dfe_document)

    def _search_distribution(self, company, access_key):
        try:
            company._dfe_search_specific_document("nfe", access_key=access_key)
        except UserError:
            raise
        except Exception as error:  # pylint: disable=broad-except
            _logger.warning("DF-e query of %s failed", access_key, exc_info=True)
            raise UserError(
                _(
                    "The distribution service could not be reached now. Try "
                    "again later or upload the XML file of the note."
                )
            ) from error

    def _find_dfe_document(self, access_key, company):
        return (
            self.env["l10n_br_fiscal_dfe.document"]
            .sudo()
            .search(
                [("access_key", "=", access_key), ("company_id", "=", company.id)],
                limit=1,
            )
        )

    def _ask_acknowledgement(self, dfe_document):
        if dfe_document.manifestation_status != "sem_manifestacao":
            dfe_document._dfe_import_request()
            return self._notification(
                _("Waiting for the XML"),
                _(
                    "The acknowledgement was already registered. The fiscal "
                    "document will be created when the complete XML arrives."
                ),
                "info",
            )
        emission = dfe_document.document_emission_date
        if emission and fields.Datetime.now() - emission > timedelta(
            days=ACKNOWLEDGEMENT_DAYS
        ):
            raise UserError(
                _(
                    "The acknowledgement is only possible until %s days after "
                    "the authorization. Upload the XML file instead."
                )
                % ACKNOWLEDGEMENT_DAYS
            )
        self.write(
            {
                "state": "confirm",
                "dfe_document_id": dfe_document.id,
                "confirm_message": _(
                    "The complete XML is only released after the acknowledgement "
                    "of the operation (ciência), an event registered at the tax "
                    "authority that obliges the company to register the final "
                    "manifestation afterwards. Register it?"
                ),
            }
        )
        return {
            "name": _("Import Fiscal Document"),
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "views": [(False, "form")],
            "view_mode": "form",
            "target": "new",
        }

    def _documents_action(self, documents):
        allowed = list(self.env.context.get("allowed_company_ids") or [])
        allowed = allowed or self.env.companies.ids
        allowed += [cid for cid in documents.company_id.ids if cid not in allowed]
        action = {
            "name": _("Imported Documents"),
            "type": "ir.actions.act_window",
            "res_model": "l10n_br_fiscal.document",
            "target": "current",
            "context": {"allowed_company_ids": allowed},
        }
        if len(documents) == 1:
            action.update(
                {
                    "res_id": documents.id,
                    "views": [(False, "form")],
                    "view_mode": "form",
                }
            )
        else:
            list_view = self.env.ref("l10n_br_fiscal_dfe_import.document_import_tree")
            action.update(
                {
                    "domain": [("id", "in", documents.ids)],
                    "views": [(list_view.id, "tree"), (False, "form")],
                    "view_mode": "tree,form",
                }
            )
        return action

    def _notification(self, title, message, level, sticky=False, action=None):
        params = {
            "title": title,
            "message": message,
            "type": level,
            "sticky": sticky,
            "next": action or {"type": "ir.actions.act_window_close"},
        }
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": params,
        }
