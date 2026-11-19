# Copyright (C) 2023  Felipe Zago Rodrigues - Kmee
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import base64
import io
import logging
import zipfile

from erpbrasil.base.fiscal.cnpj_cpf import validar_cnpj, validar_cpf
from erpbrasil.base.fiscal.edoc import detectar_chave_edoc
from erpbrasil.base.misc import punctuation_rm

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from ..constants.fiscal import (
    DOCUMENT_ISSUER_COMPANY,
    DOCUMENT_ISSUER_PARTNER,
    DOCUMENT_STATE_CANCEL,
    FISCAL_IN,
    FISCAL_IN_OUT,
    FISCAL_OUT,
)

_logger = logging.getLogger(__name__)

try:
    from xsdata.formats.dataclass.parsers import XmlParser
except ImportError:
    _logger.error(_("xsdata Python lib not installed!"))


class DocumentImportWizard(models.TransientModel):
    _name = "l10n_br_fiscal.document.import.wizard"
    _description = "Import Document Wizard"
    _inherit = "l10n_br_fiscal.base.wizard.mixin"

    company_id = fields.Many2one(
        comodel_name="res.company",
        string="Company",
        default=lambda self: self.env.company.id,
    )

    file = fields.Binary(string="File to Import")

    file_name = fields.Char()

    allow_product_creation = fields.Boolean(
        string="Create unmapped products",
        default=False,
        help="If enabled, products that don't match an existing record will be"
        " automatically created during import. If disabled (default), no product"
        " is created: the line of an unmapped product stays pending until you"
        " choose its product in the product lines above or in the document.",
    )

    file_is_zip = fields.Boolean(
        compute="_compute_file_is_zip",
        help="Technical: the file is a zip archive with several fiscal files. Each "
        "note resolves its own operation, and the wizard has no preview to show.",
    )

    batch_errors = fields.Text(
        readonly=True,
        help="The files of a zip archive that could not be imported, with the "
        "reason of each one.",
    )

    date_in_out = fields.Datetime(
        default=fields.Datetime.now,
        help="Effective incoming/outgoing date of the goods (DT_E_S in the "
        "SPED bookkeeping). Defaults to today; adjust it when the physical "
        "receipt happened on another date.",
    )

    imported_products_ids = fields.One2many(
        string="Imported Products",
        comodel_name="l10n_br_fiscal.document.import.wizard.line",
        inverse_name="import_xml_id",
    )

    fiscal_operation_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.operation",
        string="Fiscal Operation",
        domain="[('fiscal_operation_type', '=', fiscal_operation_type)]",
    )

    document_type = fields.Char()

    currency_id = fields.Many2one(related="company_id.currency_id")

    amount_total = fields.Monetary(
        string="Document Total",
    )

    fiscal_operation_type = fields.Selection(
        selection=FISCAL_IN_OUT,
        compute="_compute_fiscal_operation_type",
    )

    issuer_cnpj = fields.Char(string="Issuer CNPJ")
    issuer_legal_name = fields.Char()
    issuer_name = fields.Char(string="Fantasia")
    issuer_partner_id = fields.Many2one(
        comodel_name="res.partner",
    )
    issuer_type_in_out = fields.Selection(selection=FISCAL_IN_OUT, string="Issuer Type")

    destination_cnpj = fields.Char(string="Destination CNPJ")
    destination_name = fields.Char()
    destination_partner_id = fields.Many2one(
        comodel_name="res.partner",
    )
    destination_type_in_out = fields.Selection(
        selection=FISCAL_IN_OUT, string="Destination Type"
    )

    @api.depends("file")
    def _compute_file_is_zip(self):
        for wizard in self:
            wizard.file_is_zip = wizard._file_is_zip()

    @api.depends("issuer_cnpj", "company_id.cnpj_cpf")
    def _compute_fiscal_operation_type(self):
        if self.issuer_cnpj == self.company_id.cnpj_cpf:
            self.fiscal_operation_type = "out"
        else:
            self.fiscal_operation_type = "in"

    def _search_partner(self, cnpj=None, name=None, legal_name=None):
        """
        Search for a partner based on CNPJ, name, or legal name.

        This method searches for a partner in the `res.partner` model
        based on the provided CNPJ, name, or legal name.
        If a CNPJ is provided, it validates whether it is a
        company or an individual and constructs the search domain accordingly.

        If a legal name or name is provided, it constructs the
        search domain to match either the legal name or the name.
        If neither CNPJ nor legal name/name is provided, it raises a UserError.

        Args:
            cnpj (str, optional): The CNPJ or CPF of the partner.
            name (str, optional): The name of the partner.
            legal_name (str, optional): The legal name of the partner.

        Returns:
            recordset: A recordset of the found partner, limited to one result.

        Raises:
            UserError: If neither CNPJ nor legal name/name is provided.
        """
        domain = []
        if cnpj:
            if validar_cnpj(cnpj):
                domain = [("is_company", "=", True)]
            elif validar_cpf(cnpj):
                domain = [("is_company", "=", False)]
            domain.append(("cnpj_cpf_stripped", "=", punctuation_rm(cnpj)))
        elif legal_name or name:
            domain = [("is_company", "=", True)]
            domain += [
                "|",
                ("legal_name", "ilike", legal_name or name),
                ("name", "ilike", name or legal_name),
            ]
        else:
            raise UserError(_("No CNPJ or Legal Name to search for a partner!"))
        return self.env["res.partner"].search(domain, limit=1)

    def _company_from_destination_cnpj(self):
        """Company of the document, found through the CNPJ of the recipient.

        In a multi-company database the CNPJ of the destination (us, on an
        inbound document) identifies which of our companies the document
        belongs to. Only the companies the user may currently work in are
        considered.
        """
        cnpj = punctuation_rm(self.destination_cnpj or "")
        if not cnpj:
            return self.env["res.company"]
        companies = (
            self.env["res.company"]
            .sudo()
            .search([])
            .filtered(lambda company: punctuation_rm(company.cnpj_cpf or "") == cnpj)
        )
        return (companies & self.env.companies)[:1]

    def _select_company_from_destination(self):
        """Import the document in the company it is addressed to.

        Importing it in the user's current company instead would resolve the
        fiscal operations, the taxes and the accounting entries with another
        company's configuration: the taxes of the lines are then not found and
        the imported bill is wrong (or unimportable).

        Returns the company found through the CNPJ, empty when the document is
        addressed to nobody we know (the wizard keeps its current company).
        """
        company = self._company_from_destination_cnpj()
        if company and company != self.company_id:
            self.company_id = company
        return company

    def _import_block_reason(self):
        """Why the file cannot be imported (nothing is created), or False.

        Single point for the upload, the zip and the DF-e: a cancelled or
        denied note is refused here, and the importers add what they know.
        """
        self.ensure_one()
        return self.document_id._import_block_reason() if self.document_id else False

    def _import_edoc(self):
        self._select_company_from_destination()
        # the whole import runs in the company of the document: the fiscal
        # document, its operations and its taxes, and the account move that
        # l10n_br_account builds from it
        self = self.with_company(self.company_id)
        self._find_existing_document()
        reason = self._import_block_reason()
        if reason:
            raise UserError(reason)
        created = not self.document_id
        if created:
            binding, self.document_id = self._create_edoc_from_file()
        else:
            binding = self._parse_file()
        if self.date_in_out and not self.document_id.date_in_out:
            self.document_id.date_in_out = self.date_in_out
        if created:
            self._after_edoc_created(self.document_id)
        return binding, self.document_id

    def _after_edoc_created(self, document):
        """Hook for what the wizard decided and the new document must carry.

        Only a document that was just built from the file comes here: importing
        again a file whose document already exists returns that document and
        changes nothing in it, neither the review states nor what a person
        decided on its lines.
        """

    def action_import_and_open_document(self):
        if self._file_is_zip():
            documents = self._import_edoc_batch()
            if len(documents) == 1:
                self.document_id = documents
                action = self.action_open_document()
            else:
                action = {
                    "type": "ir.actions.act_window",
                    "name": _("Imported Documents"),
                    "res_model": "l10n_br_fiscal.document",
                    "view_mode": "tree,form",
                    "views": [(False, "tree"), (False, "form")],
                    "domain": [("id", "in", documents.ids)],
                }
            if self.batch_errors:
                # the files that failed are reported, and the others are open
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": _("Some files of the archive were not imported"),
                        "message": self.batch_errors,
                        "type": "warning",
                        "sticky": True,
                        "next": action,
                    },
                }
            return action
        self._import_edoc()
        return self.action_open_document()

    def _import_edoc_batch(self):
        """Import every fiscal file of the uploaded zip archive: each entry
        is processed by the regular single-file path and lands as a
        persisted document waiting for review.

        Each entry runs in its own savepoint: the entry that fails is undone
        whole (no half configured document stays in the transaction for a
        second upload to find) and reported in ``batch_errors``, and the other
        entries are imported."""
        self.ensure_one()
        documents = self.env["l10n_br_fiscal.document"]
        errors = []
        archive = zipfile.ZipFile(io.BytesIO(base64.b64decode(self.file)))
        for name in archive.namelist():
            if not name.lower().endswith(".xml"):
                continue
            try:
                with self.env.cr.savepoint():
                    entry = self.copy(
                        {"file": base64.b64encode(archive.read(name)).decode()}
                    )
                    entry._onchange_file()
                    entry._import_edoc()
                    documents |= entry.document_id
            except Exception as error:  # noqa: BLE001 - report per entry
                errors.append(f"{name}: {error}")
        self.batch_errors = "\n".join(errors) or False
        if errors and not documents:
            raise UserError(
                _("No file of the archive could be imported:\n%s") % "\n".join(errors)
            )
        if errors:
            _logger.warning("Zip import: %s file(s) skipped: %s", len(errors), errors)
        return documents

    def _destination_partner_from_binding(self, binding):
        pass

    def _create_edoc_from_file(self):
        pass  # meant to be overriden

    def _detect_document_type(self, code):
        self.document_type_id = self.env["l10n_br_fiscal.document.type"].search(
            [("code", "=", code)],
            limit=1,
        )

    def _find_existing_document(self):
        """The document this file already became, in the company it belongs to.

        The key identifies the note, but the same note lives in two documents
        when the issuer and the recipient are companies of the same database:
        the outgoing one of the issuer and the incoming one of the recipient.
        The search follows the criterion of the uniqueness of the key (company,
        issuer and key), so the import in the recipient never finds the
        outgoing document of the issuer.
        """
        key = (self.document_key or "").replace(" ", "")
        if not key:
            self.document_id = False
            return
        domain = [
            ("document_key", "=", key),
            ("company_id", "=", self.company_id.id),
            (
                "issuer",
                "=",
                DOCUMENT_ISSUER_PARTNER
                if self.fiscal_operation_type == FISCAL_IN
                else DOCUMENT_ISSUER_COMPANY,
            ),
        ]
        document = self.env["l10n_br_fiscal.document"]
        # a cancelled document does not hold the key (it is not part of the
        # uniqueness), but it is still found when it is the only one
        self.document_id = document.search(
            domain + [("state_edoc", "!=", DOCUMENT_STATE_CANCEL)], limit=1
        ) or document.search(domain, limit=1)

    @api.onchange("file")
    def _onchange_file(self):
        if self.file and not self._file_is_zip():
            self._fill_wizard_from_binding()

    def _file_is_zip(self):
        """A zip archive with several fiscal files can be imported at once:
        each entry lands as a document waiting for review."""
        if not self.file:
            return False
        return base64.b64decode(self.file)[:4] == b"PK\x03\x04"

    def _fill_wizard_from_binding(self):
        binding = self._parse_file()
        self._detect_binding(binding)
        self._extract_binding_data(binding)
        self._destination_partner_from_binding(binding)
        # the CNPJ of the destination (us) tells which company the document
        # belongs to: the import must run in that company, not in the current
        # one (see _select_company_from_destination)
        self._select_company_from_destination()
        # the existing document is the one of that company
        self._find_existing_document()
        return binding

    @api.model
    def _detect_binding(self, binding):
        """
        A pluggable method were each specialized fiscal document
        importation wizard can register itself and return a tuple
        with (the_fiscal_document_type_code, the_name_of_the_importation_wizard)
        """
        raise UserError(
            _("Importation not implemented for %s!")
            % (
                type(
                    binding,
                )
            )
        )

    def action_open_document(self):
        return {
            "name": _("Document Imported"),
            "type": "ir.actions.act_window",
            "target": "current",
            "views": [[False, "form"]],
            "res_id": self.document_id.id,
            "res_model": "l10n_br_fiscal.document",
        }

    def _extract_binding_data(self, binding):
        pass  # meant to be overriden

    def _extract_key_information(self, edoc_key):
        """TODO: Melhorar códifo da chave para não precisar
        remover o tipo de chave do prefixo:
            binding.NFe.infNFe.Id[3:]
        """
        edoc = detectar_chave_edoc(edoc_key)
        self.document_key = " ".join(edoc.partes())
        self.document_number = edoc.numero_documento.lstrip("0") or "0"
        self.document_serie = edoc.numero_serie.lstrip("0") or "0"
        self.issuer_cnpj = edoc.cnpj_cpf_emitente
        self.issuer_partner_id = self._search_partner(edoc.cnpj_cpf_emitente)
        if edoc.forma_emissao == "1":
            self.issuer_type_in_out = FISCAL_OUT
            self.destination_type_in_out = FISCAL_IN
        else:
            self.issuer_type_in_out = FISCAL_IN
            self.destination_type_in_out = FISCAL_OUT

    def _find_document_type(self, code):
        return self.env["l10n_br_fiscal.document.type"].search(
            [("code", "=", code)],
            limit=1,
        )

    def _find_fiscal_operation(self, cfop, nat_op, fiscal_operation_type):
        """try to find a matching fiscal operation via an operation line

        On an inbound document the file declares the counterparty OUTBOUND
        CFOP (5xxx/6xxx/7xxx), while the company operation lines reference
        inbound CFOPs (1xxx/2xxx/3xxx): the lookup goes through the inverse
        CFOP. On an outbound document the declared CFOP is the company one
        and is looked up directly.
        """
        cfop_record = self.env["l10n_br_fiscal.cfop"].search(
            [("code", "=", cfop)], limit=1
        )
        if fiscal_operation_type == "in":
            cfop_record = cfop_record.cfop_inverse_id
        if not cfop_record:
            return self.env["l10n_br_fiscal.operation"]
        operation_lines = self.env["l10n_br_fiscal.operation.line"].search(
            [
                ("state", "=", "approved"),
                ("fiscal_operation_type", "=", fiscal_operation_type),
                "|",
                "|",
                ("cfop_internal_id", "=", cfop_record.id),
                ("cfop_external_id", "=", cfop_record.id),
                ("cfop_export_id", "=", cfop_record.id),
            ],
        )
        for line in operation_lines:
            if line.fiscal_operation_id.name == nat_op:
                return line.fiscal_operation_id
        if operation_lines:
            return operation_lines[0].fiscal_operation_id

    def _match_uom_by_code(self, *codes):
        """Match a fiscal UoM from one or more XML unit codes (uCom/uTrib).

        Delegates to ``uom.uom._match_by_fiscal_code`` so the same matching
        is available outside the wizard (e.g. on the document lines).
        """
        return self.env["uom.uom"]._match_by_fiscal_code(*codes)

    def _parse_file(self):
        return self._parse_file_data(self.file)

    @api.model
    def _parse_file_data(self, file_data):
        # NOTE: no try and a stacktrace does help for debug/support
        return XmlParser().from_bytes(base64.b64decode(file_data))
