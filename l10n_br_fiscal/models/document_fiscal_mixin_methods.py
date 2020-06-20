# Copyright (C) 2019  Renato Lima - Akretion <renato.lima@akretion.com.br>
# Copyright (C) 2020  Luis Felipe Mileo - KMEE <mileo@kmee.com.br>
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, models, _
from odoo.exceptions import UserError

from ..constants.fiscal import (
    COMMENT_TYPE_FISCAL,
    COMMENT_TYPE_COMMERCIAL,
)


class FiscalDocumentMixinMethods(models.AbstractModel):
    _name = 'l10n_br_fiscal.document.mixin.methods'
    _description = 'Document Fiscal Mixin Methods'

    @api.multi
    def _prepare_br_fiscal_dict(self, default=False):
        self.ensure_one()
        fields = self.env["l10n_br_fiscal.document.mixin"]._fields.keys()

        # we now read the record fiscal fields except the m2m tax:
        vals = self._convert_to_write(self.read(fields)[0])

        # remove id field to avoid conflicts
        vals.pop('id', None)

        if default:  # in case you want to use new rather than write later
            return {"default_%s" % (k,): vals[k] for k in vals.keys()}
        return vals

    def _document_comment_vals(self):
        return {
            'user': self.env.user,
            'ctx': self._context,
            'doc': self,
        }

    def document_comment(self):
        for d in self:
            # Fiscal Comments
            fsc_comments = []
            fsc_comments.append(d.fiscal_additional_data or '')
            fsc_comments.append(d.comment_ids.filtered(
                lambda c: c.comment_type == COMMENT_TYPE_FISCAL
                ).compute_message(d._document_comment_vals()) or '')
            d.fiscal_additional_data = ', '.join(
                [c for c in fsc_comments if c])

            # Commercial Coments
            com_comments = []
            com_comments.append(d.customer_additional_data or '')
            com_comments.append(d.comment_ids.filtered(
                lambda c: c.comment_type == COMMENT_TYPE_COMMERCIAL
                ).compute_message(d._document_comment_vals()) or '')
            d.customer_additional_data = ', '.join(
                [c for c in com_comments if c])
            d.line_ids.document_comment()

    @api.onchange('fiscal_operation_id')
    def _onchange_fiscal_operation_id(self):
        if self.fiscal_operation_id:
            self.operation_name = self.fiscal_operation_id.name
            self.comment_ids = self.fiscal_operation_id.comment_ids

    def check_financial(self):
        for record in self:
            if not record.env.context.get('action_document_confirm'):
                continue
            elif record.amount_missing_payment_value > 0:
                if not record.payment_term_id:
                    raise UserError(
                        _("O Valor dos lançamentos financeiros é "
                          "menor que o valor da nota."),
                    )
                else:
                    record.generate_financial()

    def generate_financial(self):
        for record in self:
            if record.payment_term_id and self.company_id and self.currency_id:
                record.financial_ids.unlink()
                record.fiscal_payment_ids.unlink()
                vals = {
                    'payment_term_id': self.payment_term_id.id,
                    'amount': self.amount_missing_payment_value,
                    'currency_id': self.currency_id.id,
                    'company_id': self.company_id.id,
                }
                vals.update(self.fiscal_payment_ids._compute_payment_vals(
                    payment_term_id=self.payment_term_id,
                    currency_id=self.currency_id,
                    company_id=self.company_id,
                    amount=self.amount_missing_payment_value, date=self.date)
                )
                self.fiscal_payment_ids = self.fiscal_payment_ids.new(vals)
                for line in self.fiscal_payment_ids.mapped('line_ids'):
                    line.document_id = self

            elif record.fiscal_payment_ids:
                record.financial_ids.unlink()
                record.fiscal_payment_ids.unlink()

    @api.onchange("fiscal_payment_ids", "payment_term_id")
    def _onchange_fiscal_payment_ids(self):
        financial_ids = []

        for payment in self.fiscal_payment_ids:
            for line in payment.line_ids:
                financial_ids.append(line.id)
        self.financial_ids = [(6, 0, financial_ids)]

    # @api.onchange("payment_term_id", "company_id", "currency_id",
    #               "amount_missing_payment_value", "date")
    # def _onchange_payment_term_id(self):
    #     if (self.payment_term_id and self.company_id and
    #             self.currency_id):
    #
    #         self.financial_ids.unlink()
    #
    #         vals = {
    #             'payment_term_id': self.payment_term_id.id,
    #             'amount': self.amount_missing_payment_value,
    #             'currency_id': self.currency_id.id,
    #             'company_id': self.company_id.id,
    #          }
    #         vals.update(self.fiscal_payment_ids._compute_payment_vals(
    #             payment_term_id=self.payment_term_id, currency_id=self.currency_id,
    #             company_id=self.company_id,
    #             amount=self.amount_missing_payment_value, date=self.date)
    #         )
    #         self.fiscal_payment_ids = self.fiscal_payment_ids.new(vals)
    #         for line in self.fiscal_payment_ids.mapped('line_ids'):
    #             line.document_id = self
