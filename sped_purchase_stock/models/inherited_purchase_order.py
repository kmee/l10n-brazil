# -*- coding: utf-8 -*-
# Copyright 2017 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).



from odoo import api, fields, models, _


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.multi
    def button_approve(self, force=False):
        super(PurchaseOrder, self).button_approve(force)
        self._create_picking()
        if self.company_id.po_lock == 'lock':
            self.write({'state': 'done'})
        return {}
