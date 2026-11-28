# Copyright 2026 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    DOCUMENT_STATE_DRAFT,
    EDOC_PURPOSE_AJUSTE,
    EDOC_PURPOSE_DEVOLUCAO,
)

NFE_OUT = "1"
BRAZIL_BC_CODE = "1058"
ICMS_ORIGIN_FOREIGN = "1"


class FiscalDocument(models.Model):
    _inherit = "l10n_br_fiscal.document"

    mirror_document = fields.Boolean(
        copy=False,
        help="The taxes of the lines are kept as copied from the original"
        " document and are not computed again.",
    )

    original_document_id = fields.Many2one(
        comodel_name="l10n_br_fiscal.document",
        string="Original Document",
        copy=False,
    )

    mirror_document_ids = fields.One2many(
        comodel_name="l10n_br_fiscal.document",
        inverse_name="original_document_id",
        string="Mirror Documents",
        copy=False,
    )

    mirror_document_count = fields.Integer(compute="_compute_mirror_document_count")

    payment_mode_id = fields.Many2one(
        comodel_name="account.payment.mode",
        string="Payment Mode",
        ondelete="restrict",
        help="Used in the NF-e payment (detPag) of documents without invoice.",
    )

    @api.depends("mirror_document_ids")
    def _compute_mirror_document_count(self):
        for document in self:
            document.mirror_document_count = len(document.mirror_document_ids)

    def _prepare_mirror_document_vals(self):
        self.ensure_one()
        lines = self.fiscal_line_ids.sorted("id").with_context(mirror_copy=True)
        return {
            "mirror_document": True,
            "issuer": "company",
            "original_document_id": self.id,
            "nfe40_procEmi": "0",
            "nfe40_retirada": False,
            "fiscal_line_ids": [
                Command.create(line_vals)
                for line_vals in lines.copy_data()
                if line_vals
            ],
        }

    def action_create_mirror_document(self):
        self.ensure_one()
        mirror = self.copy(self._prepare_mirror_document_vals())
        if mirror.partner_id.country_id.bc_code != BRAZIL_BC_CODE:
            mirror.fiscal_line_ids.write({"icms_origin": ICMS_ORIGIN_FOREIGN})
        return self.action_open_documents(mirror)

    def action_open_mirror_documents(self):
        self.ensure_one()
        return self.action_open_documents(self.mirror_document_ids)

    def action_open_original_document(self):
        self.ensure_one()
        return self.action_open_documents(self.original_document_id)

    @api.model
    def action_open_documents(self, documents):
        action = self.env["ir.actions.actions"]._for_xml_id(
            "l10n_br_fiscal.document_all_action"
        )
        if len(documents) == 1:
            action["views"] = [
                (self.env.ref("l10n_br_fiscal.document_form").id, "form")
            ]
            action["res_id"] = documents.id
        else:
            action["domain"] = [("id", "in", documents.ids)]
        return action

    def _is_document_payment_only(self):
        self.ensure_one()
        return bool(not self.move_ids and self.payment_mode_id)

    def _is_without_payment(self):
        res = super()._is_without_payment()
        if res and self._is_document_payment_only():
            return (
                self.edoc_purpose in (EDOC_PURPOSE_DEVOLUCAO, EDOC_PURPOSE_AJUSTE)
                or not self.amount_financial_total
                or self.nfe40_tpNF != NFE_OUT
                or self.payment_mode_id.fiscal_payment_mode == "90"
            )
        return res

    @api.depends("payment_mode_id")
    def _compute_nfe40_detpag(self):
        result = super()._compute_nfe40_detpag()
        for document in self.filtered(
            lambda d: d._is_document_payment_only() and d._need_compute_nfe_tags()
        ):
            if not document._is_without_payment():
                document.nfe40_detPag.write(
                    {"nfe40_tPag": document.payment_mode_id.fiscal_payment_mode or ""}
                )
        return result

    @api.constrains("nfe40_detPag", "state_edoc", "payment_mode_id")
    def _check_fiscal_payment_mode(self):
        own = self.filtered(lambda d: d._is_document_payment_only())
        result = super(FiscalDocument, self - own)._check_fiscal_payment_mode()
        for document in own:
            if (
                document.state_edoc == DOCUMENT_STATE_DRAFT
                or not document._need_compute_nfe_tags()
                or document._is_without_payment()
            ):
                continue
            if not document.payment_mode_id.fiscal_payment_mode:
                raise UserError(
                    _(
                        "Payment Mode %(mode)s should have a Fiscal Payment Mode"
                        " filled to be used in the Fiscal Document!",
                        mode=document.payment_mode_id.name,
                    )
                )
        return result
