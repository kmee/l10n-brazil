# Copyright (C) 2020  Gabriel Cardoso de Faria <gabriel.cardoso@kmee.com.br>
# Copyright (C) 2021  Magno Costa - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _is_picking_by_fiscal_operation(self):
        self.ensure_one()
        return bool(
            self.sale_line_id
            and self.sale_line_id.order_id.company_id.sale_picking_by_fiscal_operation
        )

    def _key_assign_picking(self):
        keys = super()._key_assign_picking()
        if self._is_picking_by_fiscal_operation():
            keys += (self.fiscal_operation_id,)
        return keys

    def _search_picking_for_assignation_domain(self):
        domain = super()._search_picking_for_assignation_domain()
        if self._is_picking_by_fiscal_operation():
            domain.append(("fiscal_operation_id", "=", self.fiscal_operation_id.id))
        return domain

    def _get_new_picking_values(self):
        # IMPORTANTE: a sequencia de update dos dicionarios quando o
        # partner_shipping_id é diferente, o metodo do fiscal está
        # sobre escrevendo o partner_id e acaba criando um picking
        # sem o partner_id caso esse dict atualize o do super
        values = {}
        fiscal_operation = False
        if self.sale_line_id:
            if self.sale_line_id.order_id.fiscal_operation_id:
                fiscal_operation = self.sale_line_id.order_id.fiscal_operation_id
                values = self.sale_line_id.order_id._prepare_br_fiscal_dict()

        values.update(super()._get_new_picking_values())
        # self is a recordset, possibly with different fiscal operations
        # so we use the fiscal_operation from the SO for the picking:
        if fiscal_operation and self[:1]._is_picking_by_fiscal_operation():
            # The pickings are split by fiscal operation, so all the moves
            # have the same one
            fiscal_operation = self[0].fiscal_operation_id or fiscal_operation
        if fiscal_operation:
            values.update({"fiscal_operation_id": fiscal_operation.id})

        return values

    def _get_fiscal_partner(self):
        """
        Use partner_invoice_id if different from partner
        """
        self.ensure_one()
        partner = super()._get_fiscal_partner()
        if self.sale_line_id:
            if partner != self.sale_line_id.order_id.partner_invoice_id:
                partner = self.sale_line_id.order_id.partner_invoice_id
        return partner
