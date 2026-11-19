# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import logging
import zipfile
from io import BytesIO

from erpbrasil.base.fiscal.cnpj_cpf import formata

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .product_product import NO_CREATE_CONTEXT_KEY

_logger = logging.getLogger(__name__)

PROTOCOL_AUTHORIZED = ("100", "150")
PROTOCOL_CANCELLED = ("101", "151", "155")
PROTOCOL_DENIED = ("110", "205", "301", "302", "303")
DFE_STATE_DENIED = "2"
DFE_STATE_CANCELLED = "3"


def _value(node):
    return getattr(node, "value", node)


class Document(models.Model):
    _inherit = "l10n_br_fiscal.document"

    import_warning = fields.Text(
        compute="_compute_import_warning",
        help="What the imported document still lacks to be reviewed.",
    )

    @api.depends(
        "imported_document",
        "fiscal_operation_id",
        "fiscal_line_ids.import_ncm_code",
        "fiscal_line_ids.uom_id",
        "fiscal_line_ids.import_uom_id",
        "fiscal_line_ids.partner_uom_code",
    )
    def _compute_import_warning(self):
        for document in self:
            messages = []
            if document.imported_document:
                if not document.fiscal_operation_id:
                    messages.append(
                        _(
                            "No fiscal operation matches the CFOP of the issuer: "
                            "choose the fiscal operation of the document and the "
                            "operation line of each line."
                        )
                    )
                for line in document.fiscal_line_ids.filtered(
                    lambda line: line.import_ncm_code and not line.ncm_id
                ):
                    messages.append(
                        _("%(line)s: the NCM %(ncm)s is not in the registry.")
                        % {"line": line.name, "ncm": line.import_ncm_code}
                    )
                for line in document.fiscal_line_ids.filtered(
                    lambda line: line._dfe_unit_unconfirmed()
                ):
                    messages.append(
                        _("%(line)s: the unit %(uom)s has no match in the units.")
                        % {"line": line.name, "uom": line.partner_uom_code}
                    )
            document.import_warning = "\n".join(messages) or False

    @api.model
    def dfe_import_files(self, files, warnings=None):
        """Import NF-e XML files as draft fiscal documents.

        :param files: iterable of (file name, content in bytes); a zip file
            stands for the files it contains.
        :param warnings: optional list that receives (file name, message) of
            the files whose note was already imported (the document returned
            is the existing one).
        :return: (documents, errors): the documents created or already
            imported, and a list of (file name, message) of the files that
            were not imported. Each file runs in its own savepoint.
        """
        documents = self.browse()
        errors = []
        for name, content in self._dfe_import_expand(files):
            try:
                with self.env.cr.savepoint():
                    document, created = self._dfe_import_file(name, content)
                    documents |= document
                    if not created and warnings is not None:
                        warnings.append(
                            (
                                name,
                                _(
                                    "This note was already imported; the "
                                    "existing document was opened."
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
        return documents, errors

    @api.model
    def _dfe_import_expand(self, files):
        for name, content in files:
            if not zipfile.is_zipfile(BytesIO(content)):
                yield name, content
                continue
            with zipfile.ZipFile(BytesIO(content)) as archive:
                for member in archive.infolist():
                    if not member.is_dir():
                        yield f"{name}/{member.filename}", archive.read(member)

    @api.model
    def _dfe_import_file(self, name, content):
        try:
            binding = self.env[
                "l10n_br_fiscal.document.import.wizard"
            ]._parse_file_data(base64.b64encode(content))
        except Exception as error:  # pylint: disable=broad-except
            raise UserError(_("The file is not a valid NF-e XML.")) from error
        nfe = getattr(binding, "NFe", binding)
        inf_nfe = getattr(nfe, "infNFe", None)
        if inf_nfe is None or str(_value(inf_nfe.ide.mod)) != "55":
            raise UserError(_("Only NF-e (model 55) XML files can be imported."))
        self._dfe_import_check_protocol(binding)
        company = self._dfe_import_company(inf_nfe)
        access_key = inf_nfe.Id[3:]
        existing = self.with_company(company).search(
            [("document_key", "=", access_key), ("company_id", "=", company.id)],
            limit=1,
        )
        if existing:
            return existing, False
        self._dfe_import_check_dfe_state(access_key, company)
        last_partner = self.env["res.partner"].search([], order="id desc", limit=1)
        document = (
            self.with_company(company)
            .with_context(**{NO_CREATE_CONTEXT_KEY: True})
            .import_binding_nfe(binding, edoc_type="in")
        )
        if not document.document_type_id:
            document.document_type_id = self.env.ref("l10n_br_fiscal.document_55")
        document._dfe_import_attach_xml(content)
        document._dfe_import_restore_ncm()
        document._init_import_states()
        document._dfe_import_suggest_operation(inf_nfe)
        document._dfe_import_apply_depara()
        document._dfe_import_pending_units()
        new_partners = (
            self.env["res.partner"]
            .with_context(active_test=False)
            .search([("id", ">", last_partner.id)])
        )
        if new_partners:
            document.message_post(
                body=_("Partners created by the import: %s.")
                % ", ".join(new_partners.mapped("display_name"))
            )
        return document, True

    def _dfe_import_restore_ncm(self):
        """The NCM of an imported line is the one of the file: matching a
        product (that may have no NCM) must not replace it."""
        ncm_model = self.env["l10n_br_fiscal.ncm"]
        for line in self.fiscal_line_ids.filtered("import_ncm_code"):
            ncm = ncm_model.search(
                [("code_unmasked", "=", line.import_ncm_code)], limit=1
            )
            if ncm and line.ncm_id != ncm:
                line.ncm_id = ncm

    def _dfe_import_pending_units(self):
        """A unit with no match is not replaced by the unit of the product: the
        line stays without unit and awaits review."""
        self.ensure_one()
        uom_model = self.env["uom.uom"]
        for line in self.fiscal_line_ids.filtered("partner_uom_code"):
            if not uom_model._match_by_fiscal_code(line.partner_uom_code):
                line.uom_id = False
            if line._dfe_unit_unconfirmed():
                line.import_state = "pending"

    def action_confirm_suggestions(self):
        """Resolve in a batch the lines whose product is a suggestion: the
        confirmation of the reviewer. A line whose declared unit was not
        confirmed is left for the review."""
        skipped = self.env["l10n_br_fiscal.document.line"]
        for document in self:
            matched = document.fiscal_line_ids.filtered(
                lambda line: line.import_state == "matched"
            )
            skipped |= matched.filtered(lambda line: line._dfe_unit_unconfirmed())
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

    def _dfe_import_apply_depara(self):
        """Resolve the lines whose product the buyer already mapped for this
        supplier (a previous human decision). A product found only by internal
        code, barcode or name stays a suggestion."""
        self.ensure_one()
        uom_model = self.env["uom.uom"]
        supplierinfo = self.env["product.supplierinfo"].sudo()
        for line in self.fiscal_line_ids:
            code = line._get_partner_product_code()
            info = code and supplierinfo.search(
                [
                    ("partner_id", "=", self.partner_id.id),
                    ("product_code", "=", code),
                ],
                limit=1,
            )
            product = info and (
                info.product_id or info.product_tmpl_id.product_variant_ids[:1]
            )
            if not product:
                continue
            line.product_id = product
            declared = uom_model._match_by_fiscal_code(line.partner_uom_code)
            if declared and info.partner_uom_id == declared:
                line._apply_import_depara(
                    product=product,
                    uom=product.uom_po_id,
                    factor=info.partner_uom_factor,
                )
            elif declared and declared == product.uom_po_id:
                line._apply_import_depara(product=product, uom=declared, factor=1.0)
            elif line.uom_id:
                line.import_state = "matched"

    def _dfe_import_suggest_operation(self, inf_nfe):
        """Suggest the inbound operation of the document and of each line from
        the CFOP declared by the issuer. Prices, quantities and taxes of the
        imported lines are protected from the recompute."""
        self.ensure_one()
        wizard = self.env["l10n_br_fiscal.document.import.wizard"]
        nature = inf_nfe.ide.natOp
        operation = wizard._find_fiscal_operation(
            wizard._most_common_cfop(inf_nfe), nature, "in"
        )
        if not operation:
            return
        self.fiscal_operation_id = operation
        for line in self.fiscal_line_ids:
            operation_line = wizard._find_fiscal_operation_line(
                line.partner_cfop_id.code, nature, "in"
            )
            line.fiscal_operation_id = operation_line.fiscal_operation_id or operation
            if operation_line:
                line.fiscal_operation_line_id = operation_line

    @api.model
    def _dfe_import_check_protocol(self, binding):
        protocol = getattr(binding, "protNFe", None)
        if protocol is None:
            return
        status = str(protocol.infProt.cStat)
        if status in PROTOCOL_CANCELLED:
            raise UserError(_("This NF-e was cancelled by the issuer."))
        if status in PROTOCOL_DENIED:
            raise UserError(_("This NF-e was denied by the tax authority."))
        if status not in PROTOCOL_AUTHORIZED:
            raise UserError(_("This NF-e is not authorized (status %s).") % status)

    @api.model
    def _dfe_import_company(self, inf_nfe):
        recipient = inf_nfe.dest and (inf_nfe.dest.CNPJ or inf_nfe.dest.CPF)
        company = self.env["res.company"].sudo()
        if recipient:
            company = company.search(
                [("partner_id.cnpj_cpf_stripped", "=", recipient)], limit=1
            )
        if not company:
            raise UserError(
                _("The recipient %s is not a company of this database.")
                % (formata(recipient) if recipient else _("(none)"))
            )
        if not self.env.su and company not in self.env.user.company_ids:
            raise UserError(
                _("You have no access to the company %s, recipient of the file.")
                % company.display_name
            )
        if company not in self.env.companies:
            raise UserError(
                _(
                    "The note is addressed to the company %s, which is not selected "
                    "in the company switcher. Select it (or switch to it) and "
                    "import again."
                )
                % company.display_name
            )
        return company

    @api.model
    def _dfe_import_check_dfe_state(self, access_key, company):
        dfe_document = (
            self.env["l10n_br_fiscal_dfe.document"]
            .sudo()
            .search(
                [("access_key", "=", access_key), ("company_id", "=", company.id)],
                limit=1,
            )
        )
        if dfe_document.document_state == DFE_STATE_CANCELLED:
            raise UserError(_("This NF-e was cancelled by the issuer."))
        if dfe_document.document_state == DFE_STATE_DENIED:
            raise UserError(_("This NF-e was denied by the tax authority."))

    def _dfe_import_attach_xml(self, content):
        self.ensure_one()
        self.original_xml_file_id = self.env["ir.attachment"].create(
            {
                "name": f"NFe-Importada-{self.document_key}.xml",
                "datas": base64.b64encode(content),
                "description": "XML NFe - Importada por XML",
                "res_model": self._name,
                "res_id": self.id,
            }
        )
