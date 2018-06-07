# -*- coding: utf-8 -*-
# Copyright (C) 2009  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import ast

from openerp import models, fields, api, _
from openerp.exceptions import Warning as UserError


class StockInvoiceOnShippingRelatedDocument(models.TransientModel):
    _name = 'stock.invoice.onshipping.related.document'

    origin_id = fields.Many2one(
        ondelete='cascade',
        comodel_name='stock.invoice.onshipping',
    )

    fiscal_doc_ref = fields.Reference(
        selection="_fiscal_doc_ref_selection",
        readonly=False,
        required=True,
        string=u'Documento Fiscal',
    )

    document_model = fields.Char(
        string=u"Tipo de Documento",
        compute="compute_all",
    )

    document_type = fields.Char(compute="compute_all")

    document_date = fields.Datetime(
        string=u"Data",
        compute="compute_all"
    )

    document_partner_id = fields.Many2one(
        string=u"Parceiro",
        comodel_name='res.partner',
        compute="compute_all"
    )

    document_amount = fields.Char(
        string=u"Valor",
        compute="compute_all",
    )

    access_key = fields.Char(compute="compute_all")

    @api.multi
    @api.depends("fiscal_doc_ref")
    def compute_all(self):
        model_map = dict(self._fiscal_doc_ref_selection())
        for record in self:
            if not record.fiscal_doc_ref:
                continue
            record.document_model = model_map[record.fiscal_doc_ref._name]
            method_name = "compute_all_for_" + record.fiscal_doc_ref._table
            getattr(record, method_name)()

    @api.multi
    def compute_all_for_account_invoice(self):
        self.document_type = "nfe"
        document = self.fiscal_doc_ref
        self.document_date = document.date_invoice
        self.document_partner_id = document.partner_id
        self.document_amount = document.amount_total
        self.access_key = document.nfe_access_key

    @api.model
    def get_picking_document_relationships(self):
        return [
            'move_lines.origin_returned_move_id.picking_id.invoice_ids',
        ]

    @api.multi
    def _fiscal_doc_ref_selection(self):
        model_names = [
            self.env['stock.picking'].mapped(relationship)._name
            for relationship in self.get_picking_document_relationships()
        ]
        selection = [
            (record['model'], record['display_name'])
            for record in self.env['ir.model'].search(
                [('model', 'in', model_names)]
            )
        ]
        return selection

    @api.model
    def create_for_picking_ids(self, pickings):
        result = self.browse()
        for relationship in self.get_picking_document_relationships():
            for record in pickings.mapped(relationship):
                item = self.create(dict(
                    fiscal_doc_ref="{record._name},{record.id}".format(
                        record=record
                    )
                ))
                result |= item
                # Why is this needed? Apparently the compute_all() method is
                # not being called on the .create() above :-(
                item.compute_all()
        return result


class StockInvoiceOnShipping(models.TransientModel):
    _inherit = 'stock.invoice.onshipping'

    def active_picking_ids(self):
        context = self.env.context
        return self.env['stock.picking'].browse(context.get('active_ids'))

    @api.multi
    def _related_document_ids_default(self):
        picking_ids = self.active_picking_ids()
        related = self.env['stock.invoice.onshipping.related.document']
        related = related.create_for_picking_ids(picking_ids)
        # Do not return `related` directly since `.origin_id` is `False`
        # and self.id is False during `.default_get()` on the browser UI.
        # Instead, we have to return the One2many commands for creating them.
        result = [(0, None, vals) for vals in related.read()]
        return result

    journal_id = fields.Many2one(
        'account.journal', 'Destination Journal',
        domain="[('type', '=', journal_type)]")
    fiscal_category_journal = fields.Boolean(
        u'Diário da Categoria Fiscal', default=True)

    related_document_ids = fields.One2many(
        string=u'Related Documents',
        comodel_name='stock.invoice.onshipping.related.document',
        inverse_name='origin_id',
        default=_related_document_ids_default,
    )

    @api.multi
    def open_invoice(self):
        context = dict(self.env.context)
        for wizard in self:
            fiscal_document_code = (wizard.journal_id.company_id.
                                    product_invoice_id.code)
            context.update(
                {'fiscal_document_code': fiscal_document_code})
        result = super(StockInvoiceOnShipping,
                       self.with_context(context)).open_invoice()
        if result.get('context'):
            super_context = ast.literal_eval(result.get('context'))
            super_context.update(context)
            result['context'] = str(super_context)
        return result

    @api.multi
    def _get_related_fiscal_documents(self):
        self.ensure_one()
        return [
            dict(
                invoice_related_id=related_documents.fiscal_doc_ref.id,
                document_type=related_documents.document_type,
                access_key=related_documents.access_key,
            )
            for related_documents in self.related_document_ids
        ]

    @api.multi
    def create_invoice(self):
        self.ensure_one()
        context = dict(self.env.context)

        picking = self.active_picking_ids()
        #
        # Permite o faturamento com usuário de outra empresa, desde que o mesmo
        # tenha acesso a outra empresa, mas no momento não esteja logado com
        # a empresa do picking.
        #
        context['force_company'] = picking.company_id.id

        journal_id = picking.with_context(
            context).fiscal_category_id.property_journal
        fiscal_document_code = picking.company_id.product_invoice_id.code
        context.update(
            fiscal_document_code=fiscal_document_code,
            related_fiscal_documents=self._get_related_fiscal_documents(),
        )
        if not journal_id:
            raise UserError(
                _('Invalid Journal!'),
                _('There is not journal defined for this company: %s in '
                  'fiscal operation: %s !') %
                (picking.company_id.name,
                 picking.fiscal_category_id.name))
        self.write({'journal_id': journal_id.id})

        result = super(StockInvoiceOnShipping,
                       self.with_context(context)).create_invoice()
        return result
