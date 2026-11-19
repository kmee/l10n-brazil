# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from xsdata.formats.dataclass.parsers import XmlParser

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal.constants.fiscal import MODELO_FISCAL_NFE
from odoo.addons.l10n_br_fiscal_edi.tools import EdiParsedFile

PROTOCOL_AUTHORIZED = ("100", "150")
PROTOCOL_CANCELLED = ("101", "151", "155")
PROTOCOL_DENIED = ("110", "205", "301", "302", "303")


def _value(node):
    return getattr(node, "value", node)


def _inf_nfe(binding):
    """The ``infNFe`` of a binding, whether it is the ``nfeProc`` or the ``NFe``."""
    return getattr(getattr(binding, "NFe", binding), "infNFe", None)


class Document(models.Model):
    _inherit = "l10n_br_fiscal.document"

    @api.model
    def _edi_import_read(self, name, content):
        if b"infNFe" not in content:
            return super()._edi_import_read(name, content)
        try:
            binding = XmlParser().from_bytes(content)
        except Exception as error:  # pylint: disable=broad-except
            raise UserError(_("The file is not a valid NF-e XML.")) from error
        inf_nfe = _inf_nfe(binding)
        if inf_nfe is None:
            return super()._edi_import_read(name, content)
        if str(_value(inf_nfe.ide.mod)) != MODELO_FISCAL_NFE:
            raise UserError(_("Only NF-e (model 55) XML files can be imported."))
        protocol = getattr(binding, "protNFe", None)
        status_code = str(_value(protocol.infProt.cStat)) if protocol else ""
        recipient = inf_nfe.dest and (inf_nfe.dest.CNPJ or inf_nfe.dest.CPF)
        issuer = inf_nfe.emit.CNPJ or inf_nfe.emit.CPF
        return EdiParsedFile(
            reader="nfe",
            document_type_code=MODELO_FISCAL_NFE,
            access_key=inf_nfe.Id[3:],
            issuer_vat=issuer,
            company_vats=tuple(
                (role, vat)
                for role, vat in (("recipient", recipient), ("issuer", issuer))
                if vat
            ),
            status=self._nfe_import_status(status_code),
            status_code=status_code,
            binding=binding,
            file_name=name,
            content=content,
        )

    @api.model
    def _nfe_import_status(self, status_code):
        if status_code in PROTOCOL_AUTHORIZED:
            return "authorized"
        if status_code in PROTOCOL_CANCELLED:
            return "cancelled"
        if status_code in PROTOCOL_DENIED:
            return "denied"
        return "unknown"

    @api.model
    def _edi_import_check(self, parsed, company):
        if parsed.reader == "nfe" and parsed.status == "unknown" and parsed.status_code:
            raise UserError(
                _("This NF-e is not authorized (status %s).") % parsed.status_code
            )
        return super()._edi_import_check(parsed, company)

    @api.model
    def _edi_import_create(self, parsed, company, role):
        if parsed.reader != "nfe":
            return super()._edi_import_create(parsed, company, role)
        document = self.import_binding_nfe(
            parsed.binding, edoc_type="out" if role == "issuer" else "in"
        )
        document.partner_operation_name = _inf_nfe(parsed.binding).ide.natOp
        return document
