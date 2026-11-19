# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import logging
import zipfile
from io import BytesIO

from erpbrasil.base.fiscal.cnpj_cpf import formata

from odoo import _, api, models
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

    @api.model
    def dfe_import_files(self, files):
        """Import NF-e XML files as draft fiscal documents.

        :param files: iterable of (file name, content in bytes); a zip file
            stands for the files it contains.
        :return: (documents, errors): the documents created or already
            imported, and a list of (file name, message) of the files that
            were not imported. Each file runs in its own savepoint.
        """
        documents = self.browse()
        errors = []
        for name, content in self._dfe_import_expand(files):
            try:
                with self.env.cr.savepoint():
                    documents |= self._dfe_import_file(name, content)
            except Exception as error:  # pylint: disable=broad-except
                _logger.info("Import of %s refused: %s", name, error)
                errors.append((name, str(error)))
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
        binding = self.env["l10n_br_fiscal.document.import.wizard"]._parse_file_data(
            base64.b64encode(content)
        )
        nfe = getattr(binding, "NFe", binding)
        inf_nfe = getattr(nfe, "infNFe", None)
        if inf_nfe is None or str(_value(inf_nfe.ide.mod)) != "55":
            raise UserError(_("Only NF-e (model 55) XML files can be imported."))
        self._dfe_import_check_protocol(binding)
        company = self._dfe_import_company(inf_nfe)
        access_key = inf_nfe.Id[3:]
        existing = self.search(
            [("document_key", "=", access_key), ("company_id", "=", company.id)],
            limit=1,
        )
        if existing:
            return existing
        self._dfe_import_check_dfe_state(access_key, company)
        issuer = inf_nfe.emit.CNPJ or inf_nfe.emit.CPF
        new_partner = not self.env["res.partner"].search_count(
            [("cnpj_cpf_stripped", "=", issuer)]
        )
        document = (
            self.with_company(company)
            .with_context(**{NO_CREATE_CONTEXT_KEY: True})
            .import_binding_nfe(binding, edoc_type="in")
        )
        if not document.document_type_id:
            document.document_type_id = self.env.ref("l10n_br_fiscal.document_55")
        document._dfe_import_attach_xml(content)
        document._init_import_states()
        if new_partner:
            document.message_post(
                body=_("Issuer partner %s created by the import.")
                % document.partner_id.display_name
            )
        return document

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
        company = self.env["res.company"]
        if recipient:
            company = company.search(
                [("partner_id.cnpj_cpf_stripped", "=", recipient)], limit=1
            )
        if not company:
            raise UserError(
                _("The recipient %s is not a company of this database.")
                % (formata(recipient) if recipient else _("(none)"))
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
