# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, fields, models
from odoo.exceptions import UserError


class DocumentImportWizard(models.TransientModel):
    _name = "l10n_br_fiscal_edi.document.import.wizard"
    _description = "Import Fiscal Documents from Files"

    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        string="Files",
        help="One file, several, or a zip with them.",
    )

    def action_import(self):
        self.ensure_one()
        if not self.attachment_ids:
            raise UserError(_("Upload at least one file."))
        # The content is read here, from the raw bytes, and without bin_size: with
        # it the web client asks for the size, and the binary fields answer the
        # size of the file instead of its content (raw included).
        attachments = self.attachment_ids.with_context(bin_size=False)
        documents, errors, warnings = self.env[
            "l10n_br_fiscal.document"
        ]._edi_import_files(
            [(attachment.name, attachment.raw) for attachment in attachments]
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
                action,
            )
        if warnings:
            return self._notification(
                _("Note already imported"),
                "\n".join(f"{name}: {message}" for name, message in warnings),
                "info",
                action,
            )
        return action

    def _documents_action(self, documents):
        """Open the document, or the list when there are several. The context
        carries the company of each one, so it opens even if it is not the current."""
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
            list_view = self.env.ref("l10n_br_fiscal_edi.document_import_tree")
            action.update(
                {
                    "domain": [("id", "in", documents.ids)],
                    "views": [(list_view.id, "tree"), (False, "form")],
                    "view_mode": "tree,form",
                }
            )
        return action

    def _notification(self, title, message, level, action):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": level,
                "sticky": True,
                "next": action,
            },
        }
