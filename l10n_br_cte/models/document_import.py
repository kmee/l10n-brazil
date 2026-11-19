# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re

from erpbrasil.base.misc import punctuation_rm
from lxml import etree
from nfelib.cte.bindings.v4_0.cte_v4_00 import Cte
from nfelib.cte.bindings.v4_0.proc_cte_v4_00 import CteProc
from xsdata.exceptions import ParserError
from xsdata.formats.dataclass.parsers import XmlParser

from odoo import _, api, models
from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal.constants.fiscal import MODELO_FISCAL_CTE
from odoo.addons.l10n_br_fiscal_edi.tools import EdiParsedFile

CTE_NAMESPACE = "http://www.portalfiscal.inf.br/cte"

# Roots of the CT-e file that is authorized (cteProc) and of the one that is not.
CTE_ROOTS = {"cteProc": CteProc, "CTe": Cte}

# Other documents of the same namespace that are not a CT-e (model 57).
NOT_IMPORTABLE_ROOTS = {
    "cteOSProc": "CT-e OS",
    "CTeOS": "CT-e OS",
    "GTVeProc": "GTV-e",
    "GTVe": "GTV-e",
    "cteSimpProc": "CT-e Simp",
    "CTeSimp": "CT-e Simp",
}

PROTOCOL_AUTHORIZED = ("100", "150")
PROTOCOL_CANCELLED = ("101", "151", "155")
PROTOCOL_DENIED = ("110", "205", "301", "302", "303")

# toma3/toma: which party of the CT-e takes the service.
TAKER_BY_CODE = {"0": "rem", "1": "exped", "2": "receb", "3": "dest"}


def _value(node):
    return getattr(node, "value", node)


def _vat(party):
    """Digits of the CNPJ or CPF of a party of the CT-e, or False."""
    if party is None:
        return False
    return punctuation_rm(getattr(party, "CNPJ", None) or getattr(party, "CPF", None))


class Document(models.Model):
    _inherit = "l10n_br_fiscal.document"

    @api.model
    def _edi_import_read(self, name, content):
        try:
            root = etree.fromstring(
                content, etree.XMLParser(resolve_entities=False, no_network=True)
            )
        except etree.XMLSyntaxError:
            return super()._edi_import_read(name, content)
        tag = etree.QName(root)
        if tag.namespace != CTE_NAMESPACE:
            return super()._edi_import_read(name, content)
        if tag.localname in NOT_IMPORTABLE_ROOTS:
            raise UserError(
                _(
                    "Only the CT-e (model 57) can be imported as a fiscal document. "
                    "The file %(name)s is a %(kind)s.",
                    name=name,
                    kind=NOT_IMPORTABLE_ROOTS[tag.localname],
                )
            )
        if tag.localname not in CTE_ROOTS:
            return super()._edi_import_read(name, content)
        try:
            binding = XmlParser().from_bytes(content, CTE_ROOTS[tag.localname])
        except ParserError:
            binding = None
        cte = getattr(binding, "CTe", None) or binding
        infcte = getattr(cte, "infCte", None)
        if infcte is None or not re.fullmatch(r"CTe\d{44}", infcte.Id or ""):
            raise UserError(_("The file %s is not a valid CT-e.") % name)
        protocol = getattr(getattr(binding, "protCTe", None), "infProt", None)
        status_code = str(protocol.cStat) if protocol is not None else ""
        return EdiParsedFile(
            reader="cte",
            document_type_code=MODELO_FISCAL_CTE,
            access_key=infcte.Id[3:],
            issuer_vat=_vat(infcte.emit),
            company_vats=self._cte_company_vats(infcte),
            status=self._cte_status(status_code),
            status_code=status_code,
            binding=binding,
            file_name=name,
            content=content,
        )

    @api.model
    def _cte_company_vats(self, infcte):
        """Who may be the company, in order: the taker of the service, the
        recipient and the sender."""
        ide = infcte.ide
        taker = None
        if getattr(ide, "toma3", None) is not None:
            party = TAKER_BY_CODE.get(str(_value(ide.toma3.toma)))
            taker = _vat(getattr(infcte, party, None)) if party else False
        elif getattr(ide, "toma4", None) is not None:
            taker = _vat(ide.toma4)
        vats = [
            ("taker", taker),
            ("recipient", _vat(getattr(infcte, "dest", None))),
            ("recipient", _vat(getattr(infcte, "rem", None))),
        ]
        return tuple((role, vat) for role, vat in vats if vat)

    @api.model
    def _cte_status(self, status_code):
        if status_code in PROTOCOL_AUTHORIZED:
            return "authorized"
        if status_code in PROTOCOL_CANCELLED:
            return "cancelled"
        if status_code in PROTOCOL_DENIED:
            return "denied"
        return "unknown"

    @api.model
    def _edi_import_create(self, parsed, company, role):
        if parsed.reader != "cte":
            return super()._edi_import_create(parsed, company, role)
        document = self.import_binding_cte(parsed.binding, edoc_type="in")
        for line in document.fiscal_line_ids:
            line.partner_cfop_id = line.cfop_id
        return document
