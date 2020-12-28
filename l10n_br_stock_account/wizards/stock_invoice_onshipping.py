# Copyright (C) 2009  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import _, api, fields, models
from odoo.exceptions import UserError


class StockInvoiceOnshipping(models.TransientModel):
    _inherit = 'stock.invoice.onshipping'

    fiscal_operation_journal = fields.Boolean(
        string='Account Jornal from Fiscal Operation',
        default=True,
    )

    group = fields.Selection(
        selection_add=[
            ('fiscal_operation', 'Fiscal Operation')],
    )

    @api.multi
    def _get_journal(self):
        """
        Get the journal depending on the journal_type
        :return: account.journal recordset
        """
        self.ensure_one()
        if self.fiscal_operation_journal:
            pickings = self._load_pickings()
            picking = fields.first(pickings)
            journal = picking.fiscal_operation_id.journal_id
            if not journal:
                raise UserError(
                    _('Invalid Journal! There is not journal defined'
                      ' for this company: %s in fiscal operation: %s !') %
                    (picking.company_id.name,
                     picking.fiscal_operation_id.name))
        else:
            journal = super()._get_journal()
        return journal

    @api.multi
    def _build_invoice_values_from_pickings(self, pickings):
        invoice, values = super()._build_invoice_values_from_pickings(pickings)
        pick = fields.first(pickings)
        fiscal_vals = pick._prepare_br_fiscal_dict()

        document_type = pick.company_id.document_type_id
        document_type_id = pick.company_id.document_type_id.id

        fiscal_vals['document_type_id'] = document_type_id

        document_serie = document_type.get_document_serie(
            pick.company_id, pick.fiscal_operation_id)
        if document_serie:
            fiscal_vals['document_serie_id'] = document_serie.id

        if pick.fiscal_operation_id and pick.fiscal_operation_id.journal_id:
            fiscal_vals['journal_id'] = pick.fiscal_operation_id.journal_id.id

        # Endereço de Entrega diferente do Endereço de Faturamento
        # so informado quando é diferente
        if fiscal_vals['partner_id'] != values['partner_id']:
            values['partner_shipping_id'] = fiscal_vals['partner_id']
        # Ser for feito o update como abaixo o campo
        # fiscal_operation_id vai vazio
        # fiscal_vals.update(values)
        values.update(fiscal_vals)
        values['fiscal_document_id'] = False

        return invoice, values

    @api.multi
    def _get_invoice_line_values(self, moves, invoice_values, invoice):
        """
        Create invoice line values from given moves
        :param moves: stock.move
        :param invoice: account.invoice
        :return: dict
        """

        values = super()._get_invoice_line_values(
            moves, invoice_values, invoice)
        move = fields.first(moves)
        fiscal_values = move._prepare_br_fiscal_dict()
        # IMPORTANTE: se for feito o
        # values.update(fiscal_values)
        # o campo price_unit fica negativo na fatura criada
        fiscal_values.update(values)

        fiscal_values['invoice_line_tax_ids'] = [
            (6, 0, self.env['l10n_br_fiscal.tax'].browse(
                fiscal_values['fiscal_tax_ids'][0][2]
            ).account_taxes().ids)
        ]

        return fiscal_values

    @api.multi
    def _get_move_key(self, move):
        """
        Get the key based on the given move
        :param move: stock.move recordset
        :return: key
        """
        key = super()._get_move_key(move)
        if move.fiscal_operation_line_id:
            # Linhas de Operações Fiscais diferentes
            # não podem ser agrupadas
            if type(key) is tuple:
                key = key + (move.fiscal_operation_line_id,)
            else:
                # TODO - seria melhor identificar o TYPE para saber se
                #  o KEY realmente é um objeto nesse caso
                key = (key, move.fiscal_operation_line_id)

        return key

    @api.multi
    def _simulate_invoice_line_onchange(self, values):
        """
        Simulate onchange for invoice line
        :param values: dict
        :return: dict
        """
        price_unit = values.pop('price_unit')
        new_values = super()._simulate_invoice_line_onchange(values.copy())
        line = self.env['account.invoice.line'].new(new_values.copy())
        line.price_unit = price_unit
        line._compute_price()
        new_values.update(line._convert_to_write(line._cache))
        values.update(new_values)
        return values
