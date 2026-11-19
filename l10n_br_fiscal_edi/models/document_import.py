# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging
import zipfile
from io import BytesIO

from erpbrasil.base.fiscal.cnpj_cpf import formata

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    DOCUMENT_ISSUER_COMPANY,
    DOCUMENT_ISSUER_PARTNER,
    DOCUMENT_STATE_DRAFT,
    FISCAL_IN,
    FISCAL_OUT,
)

from ..tools import EDI_IMPORT_NO_CREATE

_logger = logging.getLogger(__name__)

# Context key that carries, to the end of the import, the last partner that existed
# before it started: the partners above it were created by the file.
LAST_PARTNER_CONTEXT_KEY = "edi_import_last_partner_id"


class Document(models.Model):
    """Import of fiscal files into draft documents, whatever the type of the file.

    The reader of each type (NF-e, CT-e, NFS-e, MDF-e) is a module that chains
    ``_edi_import_read``, ``_edi_import_create`` and, when it needs to, the other
    steps. This module orchestrates: it reads, finds the company, refuses what must
    not enter, creates the document faithful to the file and suggests the review.
    """

    _inherit = "l10n_br_fiscal.document"

    import_warning = fields.Text(
        compute="_compute_import_warning",
        help="What the imported document still lacks to be reviewed.",
    )

    @api.depends(
        "imported_document",
        "fiscal_operation_id",
        "fiscal_amount_total",
        "fiscal_line_ids.partner_ncm_code",
        "fiscal_line_ids.ncm_id",
        "fiscal_line_ids.uom_id",
        "fiscal_line_ids.import_uom_id",
        "fiscal_line_ids.partner_uom_code",
    )
    def _compute_import_warning(self):
        for document in self:
            document.import_warning = (
                "\n".join(document._edi_import_warnings()) or False
            )

    def _edi_import_warnings(self):
        """Messages that tell what an imported document still lacks."""
        self.ensure_one()
        messages = []
        if not self.imported_document:
            return messages
        if not self.fiscal_operation_id:
            messages.append(
                _(
                    "No fiscal operation matches the CFOP of the document: choose the "
                    "fiscal operation of the document and the operation line of "
                    "each line."
                )
            )
        for line in self.fiscal_line_ids:
            if line.partner_ncm_code and not line.ncm_id:
                messages.append(
                    _("%(line)s: the NCM %(ncm)s is not in the registry.")
                    % {"line": line.name, "ncm": line.partner_ncm_code}
                )
            if line._import_unit_unconfirmed():
                messages.append(
                    _("%(line)s: the unit %(uom)s has no match in the units.")
                    % {"line": line.name, "uom": line.partner_uom_code}
                )
        return messages

    @api.model
    def _edi_import_files(self, files, dfe_document=None):
        """Import fiscal files as draft documents, each one in its own savepoint.

        :param files: list of ``(name, bytes)``; a zip stands for the files in it
        :param dfe_document: ``l10n_br_fiscal_dfe.document`` the files came from
        :return: ``(documents, errors, warnings)``; ``errors`` and ``warnings`` are
            lists of ``(name, message)``. A note that was already imported is a
            warning, and its document is returned.
        """
        documents = self.browse()
        errors, warnings = [], []
        for name, content in self._edi_import_expand(files):
            try:
                with self.env.cr.savepoint():
                    document, created = self._edi_import_file(
                        name, content, dfe_document=dfe_document
                    )
                documents |= document
                if not created:
                    warnings.append(
                        (
                            name,
                            _(
                                "This note was already imported; the existing "
                                "document was opened."
                            ),
                        )
                    )
            except UserError as error:
                _logger.info("Import of %s refused: %s", name, error)
                errors.append((name, str(error)))
            except Exception:  # pylint: disable=broad-except
                _logger.warning("Import of %s failed", name, exc_info=True)
                errors.append(
                    (
                        name,
                        _(
                            "The file could not be imported because of an "
                            "unexpected error. Send it to the support."
                        ),
                    )
                )
        return documents, errors, warnings

    @api.model
    def _edi_import_expand(self, files):
        """Yield ``(name, content)`` of each file, a zip standing for what it holds
        (one level, no folders, no ``__MACOSX/``): ``zip/file``."""
        for name, content in files:
            if not zipfile.is_zipfile(BytesIO(content)):
                yield name, content
                continue
            with zipfile.ZipFile(BytesIO(content)) as archive:
                for member in archive.infolist():
                    if member.is_dir() or member.filename.startswith("__MACOSX/"):
                        continue
                    yield f"{name}/{member.filename}", archive.read(member)

    @api.model
    def _edi_import_file(self, name, content, dfe_document=None):
        """Import one file. Return ``(document, created)``: ``created`` is False
        when the note was already imported and the existing document is returned.
        """
        parsed = self._edi_import_read(name, content)
        if parsed is None:
            raise UserError(
                _("The file %s is not a fiscal document that can be imported.") % name
            )
        company, role = self._edi_import_company(parsed)
        existing = self.with_company(company)._edi_import_find_existing(parsed, company)
        if existing:
            return existing, False
        self._edi_import_check(parsed, company)
        last_partner = self.env["res.partner"].search([], order="id desc", limit=1)
        try:
            document = (
                self.with_company(company)
                .with_context(**{EDI_IMPORT_NO_CREATE: True})
                ._edi_import_create(parsed, company, role)
            )
        except AccessError as error:
            if self.env["res.partner"].check_access_rights(
                "create", raise_exception=False
            ):
                raise
            raise UserError(self._edi_import_partner_denied(parsed)) from error
        document.with_context(
            **{LAST_PARTNER_CONTEXT_KEY: last_partner.id}
        )._edi_import_after_create(parsed, role)
        document._edi_import_suggest()
        return document, True

    @api.model
    def _edi_import_read(self, name, content):
        """Read the bytes of a file. Each reader returns an ``EdiParsedFile`` or
        calls ``super()``; the base answers that the file is not recognized."""
        return None

    @api.model
    def _edi_import_company(self, parsed):
        """Company that the file is addressed to, in the order of ``company_vats``.

        The company is looked for with sudo, because the user does not read the
        companies that are not theirs; access and company switcher are then
        checked without it, before anything is created.
        """
        company = self.env["res.company"]
        role = False
        for candidate_role, vat in parsed.company_vats:
            company = (
                self.env["res.company"]
                .sudo()
                .search([("partner_id.cnpj_cpf_stripped", "=", vat)], limit=1)
            )
            if company:
                role = candidate_role
                break
        if not company:
            raise UserError(
                _("No company of this database is the recipient or the issuer of %s.")
                % parsed.file_name
            )
        company = company.sudo(False)
        if not self.env.su and company not in self.env.user.company_ids:
            raise UserError(
                _("You have no access to the company %s, which the file is for.")
                % company.display_name
            )
        if company not in self.env.companies:
            raise UserError(
                _(
                    "The note is for the company %s, which is not selected in the "
                    "company switcher. Select it and import again."
                )
                % company.display_name
            )
        return company, role

    @api.model
    def _edi_import_partner_hint(self, parsed):
        """Name and CNPJ/CPF of the partner the file needs to be registered, as
        ``(name, vat)``. A reader that knows the name overrides it; the base knows
        only the document of the issuer."""
        return "", parsed.issuer_vat

    @api.model
    def _edi_import_partner_denied(self, parsed):
        """Message for a user who cannot create contacts when the file needs one."""
        name, vat = self._edi_import_partner_hint(parsed)
        partner = " ".join(
            part
            for part in (name, formata(vat) and f"(CNPJ/CPF {formata(vat)})")
            if part
        )
        return _(
            "The file %(file)s requires registering the partner %(partner)s, and you "
            "are not allowed to create contacts. Ask someone who can to register "
            "it, or ask for the permission, and import the file again."
        ) % {"file": parsed.file_name, "partner": partner or _("(unknown)")}

    @api.model
    def _edi_import_check(self, parsed, company):
        """Refuse what must not enter. Extended by who knows more about the file."""
        if parsed.status == "cancelled":
            raise UserError(_("This note was cancelled by the issuer."))
        if parsed.status == "denied":
            raise UserError(_("This note was denied by the tax authority."))

    @api.model
    def _edi_import_find_existing(self, parsed, company):
        return self.search(
            [("document_key", "=", parsed.access_key), ("company_id", "=", company.id)],
            limit=1,
        )

    @api.model
    def _edi_import_create(self, parsed, company, role):
        """Create the draft document from the file. Each reader answers for its
        ``parsed.reader`` and calls ``super()`` for the others."""
        raise UserError(
            _("There is no importer for the files of type %s.") % parsed.reader
        )

    def _edi_import_after_create(self, parsed, role):
        """What every imported document has, whatever the reader."""
        self.ensure_one()
        issued_by_company = role == "issuer"
        self.write(
            {
                "imported_document": True,
                "issuer": (
                    DOCUMENT_ISSUER_COMPANY
                    if issued_by_company
                    else DOCUMENT_ISSUER_PARTNER
                ),
                "fiscal_operation_type": FISCAL_OUT if issued_by_company else FISCAL_IN,
                "original_xml_file_id": self.env["ir.attachment"]
                .create(
                    {
                        "name": parsed.file_name,
                        "raw": parsed.content,
                        "res_model": self._name,
                        "res_id": self.id,
                    }
                )
                .id,
            }
        )
        floor = self.env.context.get(LAST_PARTNER_CONTEXT_KEY, 0)
        new_partners = (
            self.env["res.partner"]
            .with_context(active_test=False)
            .search([("id", ">", floor), ("create_uid", "=", self.env.uid)])
        )
        if new_partners:
            self.message_post(
                body=_("Partners created by the import: %s.")
                % ", ".join(new_partners.mapped("display_name"))
            )

    def _edi_import_suggest(self):
        """Suggest the review of the document. Safe to run again: what a person
        decided is never undone."""
        for document in self.filtered("imported_document"):
            document._init_import_states()
            document._edi_import_suggest_operation()
            if document.fiscal_operation_type == FISCAL_IN:
                document._edi_import_apply_supplier_depara()
            for line in document.fiscal_line_ids.filtered(
                lambda line: line.import_state == "matched"
                and line._import_unit_unconfirmed()
            ):
                line.import_state = "pending"

    def _edi_import_suggest_operation(self):
        """The operation of the document and of each line that has none, from the
        CFOP declared in the file: the inverse of the issuer for a document received,
        the very CFOP for a document the company issued elsewhere. Nothing is
        assigned when nothing matches: an empty operation would recompute the
        direction of the document."""
        self.ensure_one()
        direction = self.fiscal_operation_type
        if not direction:
            return
        operation_lines = self.env["l10n_br_fiscal.operation.line"]
        found = {
            line: operation_lines._find_by_issuer_cfop(
                line.partner_cfop_id, self.operation_name, direction
            )
            for line in self.fiscal_line_ids.filtered(
                lambda line: not line.fiscal_operation_line_id
            )
        }
        if not self.fiscal_operation_id:
            if direction == FISCAL_IN:
                operation = self._suggest_fiscal_operation()
            else:
                votes = [op_line.fiscal_operation_id for op_line in found.values()]
                votes = [operation for operation in votes if operation]
                operation = votes and max(set(votes), key=votes.count)
            if operation:
                self.fiscal_operation_id = operation
        if not self.fiscal_operation_id:
            return
        for line, operation_line in found.items():
            line.fiscal_operation_id = (
                operation_line.fiscal_operation_id or self.fiscal_operation_id
            )
            if operation_line:
                line.fiscal_operation_line_id = operation_line

    def _edi_import_apply_supplier_depara(self):
        """Resolve the lines whose product the buyer already mapped for this
        supplier (a previous decision of a person). A product found only by code,
        barcode or name stays a suggestion."""
        self.ensure_one()
        uom_model = self.env["uom.uom"]
        supplierinfo_model = self.env["product.supplierinfo"].sudo()
        for line in self.fiscal_line_ids.filtered(
            lambda line: line.import_state in (False, "pending", "matched")
        ):
            code = line._get_partner_product_code()
            info = code and supplierinfo_model.search(
                [("partner_id", "=", self.partner_id.id), ("product_code", "=", code)],
                limit=1,
            )
            product = info and (
                info.product_id or info.product_tmpl_id.product_variant_ids[:1]
            )
            if not product:
                continue
            line.product_id = product
            declared = uom_model._match_by_fiscal_code(line.partner_uom_code)
            learned_uom, learned_factor = line._get_supplierinfo_unit(info)
            if declared and learned_uom == declared:
                line._apply_import_depara(
                    product=product, uom=product.uom_po_id, factor=learned_factor
                )
            elif declared and declared == product.uom_po_id:
                line._apply_import_depara(product=product, uom=declared, factor=1.0)
            elif line.uom_id:
                line.import_state = "matched"

    def action_import_confirm_suggestions(self):
        """Resolve at once the lines whose product is a suggestion: the confirmation
        of whoever reviews. A line whose unit was not confirmed is left for the
        review, and the user is told how many."""
        skipped = self.env["l10n_br_fiscal.document.line"]
        for document in self:
            matched = document.fiscal_line_ids.filtered(
                lambda line: line.import_state == "matched"
            )
            skipped |= matched.filtered(lambda line: line._import_unit_unconfirmed())
            (matched - skipped).action_resolve_line()
        if not skipped:
            return True
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Some lines were not confirmed"),
                "message": _(
                    "%(count)s line(s) kept for the review: the unit declared by "
                    "the supplier has no match. Choose the unit of each one."
                )
                % {"count": len(skipped)},
                "type": "warning",
                "sticky": True,
                "next": {"type": "ir.actions.client", "tag": "reload"},
            },
        }

    def action_document_confirm(self):
        """An imported document is confirmed only when every line was reviewed.

        One that the company issued in another system is already authorized there:
        it is confirmed as authorized, never validated and sent again.
        """
        drafts = self.filtered(
            lambda doc: doc.imported_document and doc.state_edoc == DOCUMENT_STATE_DRAFT
        )
        for document in drafts:
            unresolved = document.fiscal_line_ids.filtered(
                lambda line: line.import_state in ("pending", "matched")
            )
            if unresolved:
                raise UserError(
                    _(
                        "The document %(document)s has lines that were not reviewed:"
                        "\n%(lines)s"
                    )
                    % {
                        "document": document.display_name,
                        "lines": "\n".join(unresolved.mapped("name")),
                    }
                )
        own = drafts.filtered(lambda doc: doc.issuer == DOCUMENT_ISSUER_COMPANY)
        for document in own:
            document._trigger_fsm("action_confirm_authorized")
        return super(Document, self - own).action_document_confirm()
