# Copyright (C) 2022-Today - Engenere (<https://engenere.one>).
# @author Antônio S. Pereira Neto <neto@engenere.one>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).


from odoo import _, api, fields, models
from odoo.exceptions import UserError

from odoo.addons.l10n_br_fiscal.constants.fiscal import (
    EDOC_PURPOSE_AJUSTE,
    EDOC_PURPOSE_DEVOLUCAO,
)

A_PRAZO = "1"
A_VISTA = "0"
SEM_PAGAMENTO = "90"
NFE_IN = "0"
NFE_OUT = "1"


class DocumentNfe(models.Model):

    _inherit = "l10n_br_fiscal.document"

    ##########################
    # NF-e tag: Cob
    ##########################

    nfe40_dup = fields.One2many(
        comodel_name="nfe.40.dup",
        compute="_compute_nfe40_dup",
        store=True,
        copy=False,
        readonly=False,
    )

    ##########################
    # NF-e tag: dup
    # Compute Methods
    ##########################

    @api.depends("move_ids", "move_ids.financial_move_line_ids")
    def _compute_nfe40_dup(self):
        for record in self.filtered(lambda x: x._need_compute_nfe40_dup()):
            dups_vals = []
            for count, mov in enumerate(record.move_ids.financial_move_line_ids, 1):
                dups_vals.append(
                    {
                        "nfe40_nDup": str(count).zfill(3),
                        "nfe40_dVenc": mov.date_maturity,
                        "nfe40_vDup": mov.debit,
                    }
                )
            record.nfe40_dup = [(2, dup, 0) for dup in record.nfe40_dup.ids]
            record.nfe40_dup = [(0, 0, dup) for dup in dups_vals]

    ##########################
    # NF-e tag: Pag
    ##########################

    nfe40_detPag = fields.One2many(
        comodel_name="nfe.40.detpag",
        compute="_compute_nfe40_detpag",
        store=True,
        readonly=False,
    )

    ##########################
    # NF-e tag: detPag
    # Compute Methods
    ##########################

    @api.depends(
        "issuer",
        "move_ids",
        "move_ids.payment_mode_id",
        "move_ids.payment_mode_id.fiscal_payment_mode",
        "amount_financial_total",
        "nfe40_tpNF",
    )
    def _compute_nfe40_detpag(self):
        for rec in self.filtered(lambda x: x._need_compute_nfe_tags()):
            if rec._is_without_payment():
                det_pag_vals = {
                    "nfe40_indPag": A_VISTA,
                    "nfe40_tPag": SEM_PAGAMENTO,
                    "nfe40_vPag": 0.00,
                }
            else:
                # TODO pode haver pagamento que uma parte é a vista
                # e outra a prazo, dividir em dois detPag nestes casos.
                det_pag_vals = {
                    "nfe40_indPag": A_PRAZO if rec._is_installment() > 0 else A_VISTA,
                    "nfe40_tPag": rec.move_ids.payment_mode_id.fiscal_payment_mode
                    or "",
                    "nfe40_vPag": rec.amount_financial_total,
                }
            detpag_current = {
                field: getattr(detpag, field, None)
                for detpag in rec.nfe40_detPag
                for field in det_pag_vals
            }
            if det_pag_vals != detpag_current:

                rec.nfe40_detPag = [(2, detpag, 0) for detpag in rec.nfe40_detPag.ids]
                rec.nfe40_detPag = [(0, 0, det_pag_vals)]

    ################################
    # Business Model Methods
    ################################

    def _is_installment(self):
        """checks if the payment is in cash (á vista) or in installments (a prazo)"""
        self.ensure_one()
        self.move_ids.financial_move_line_ids.mapped("date_maturity")
        moves_terms = self.move_ids.financial_move_line_ids.filtered(
            lambda move_line: move_line.date_maturity > move_line.date
        )
        return True if len(moves_terms) > 0 else False

    def _need_compute_nfe40_dup(self):
        if (
            self._need_compute_nfe_tags()
            and self.amount_financial_total > 0
            and self.nfe40_tpNF == NFE_OUT
            and self.document_type != "65"
        ):
            return True
        else:
            return False

    def _is_without_payment(self):
        if self.edoc_purpose in (EDOC_PURPOSE_DEVOLUCAO, EDOC_PURPOSE_AJUSTE):
            return True
        if not self.amount_financial_total:
            return True
        if self.nfe40_tpNF == NFE_IN:
            return True
        else:
            return False

    @api.constrains("nfe40_detPag", "state_edoc")
    def _check_fiscal_payment_mode(self):
        for rec in self:

            if (
                rec.state_edoc == "em_digitacao"
                or not rec._need_compute_nfe_tags()
                or rec._is_without_payment()
            ):
                continue

            if not rec.move_ids.payment_mode_id:
                raise UserError(_("Payment Mode cannot be empty for this NF-e/NFC-e"))
            if not rec.move_ids.payment_mode_id.fiscal_payment_mode:
                raise UserError(
                    _(
                        f"Payment Mode {rec.move_ids.payment_mode_id.name} should has "
                        "has Fiscal Payment Mode filled to be used in Fiscal Document!"
                    )
                )

    def _process_document_in_contingency(self):
        super()._process_document_in_contingency()

        if self.move_ids:
            copy_invoice = self.move_ids[0].copy()
            copy_invoice.action_post()

    @api.model_create_multi
    def create(self, vals_list):
        if self._context.get("create_from_move"):
            filtered_vals_list = []
            for values in vals_list:
                if not values.get("imported_document", False):
                    filtered_vals_list.append(values)
            documents = super().create(filtered_vals_list)
        else:
            documents = super().create(vals_list)
        if documents and self._context.get("create_from_document"):
            invoices = documents._create_account_moves()
            invoices._create_financial_lines_from_dups()
        return documents

    def _create_account_moves(self):
        self.flush()
        AccountMove = self.env["account.move"]
        invoices_to_create = []
        for document in self:
            invoices_to_create.append(
                {
                    "partner_id": document.partner_id.id,
                    "user_id": self.env.user.id,
                    "company_id": self.env.company.id,
                    "currency_id": self.env.company.currency_id.id,
                    "invoice_date": document.document_date,  # TODO: Arrumar datedue
                    "invoice_line_ids": [
                        (0, None, self._prepare_invoice_line(line))
                        for line in document.fiscal_line_ids
                    ],
                    "move_type": "in_invoice",
                    "imported_document": document.imported_document,
                }
            )
        if invoices_to_create:
            invoices = AccountMove.create(invoices_to_create)
            for document, invoice in zip(self, invoices):
                invoice.write({"fiscal_document_id": document.id})
                for invoice_line in invoice.invoice_line_ids:
                    # TODO: Não vai funcionar para notas com o mesmo produto
                    # em mais de uma linha
                    invoice_line.fiscal_document_line_id = (
                        document.fiscal_line_ids.filtered(
                            lambda fl: fl.product_id == invoice_line.product_id
                        )
                    )
        return invoices

    def _prepare_invoice_line(self, fiscal_line):
        fiscal_position = self.env["account.fiscal.position"].browse(
            fiscal_line.partner_id.property_account_position_id.id
        )
        values = fiscal_line._convert_to_write(fiscal_line.read()[0])
        # TODO: Utilizar lógica parecida com do stock.invoice.onshipping
        # para mapear account_id
        values.update(
            {
                "product_id": fiscal_line.product_id.id,
                "quantity": fiscal_line.quantity,
                "discount": fiscal_line.discount_value,
                "price_unit": fiscal_line.price_unit,
                "name": fiscal_line.name,
                # "tax_ids": [(6, 0, order_line.tax_ids_after_fiscal_position.ids)],
                "product_uom_id": fiscal_line.uom_id.id,
                "fiscal_document_line_id": fiscal_line.id,
                "account_id": fiscal_position.map_account(
                    fiscal_line.product_id.categ_id.property_account_expense_categ_id
                ).id,
            }
        )
        return values
