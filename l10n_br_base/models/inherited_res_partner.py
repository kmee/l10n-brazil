# -*- coding: utf-8 -*-
#
# Copyright 2016 Taŭga Tecnologia
#   Aristides Caldeira <aristides.caldeira@tauga.com.br>
# License AGPL-3 or later (http://www.gnu.org/licenses/agpl)
#

from __future__ import division, print_function, unicode_literals
from .base_participante import Participante
from odoo import api, fields, models


class ResPartner(Participante, models.Model):
    _inherit = 'res.partner'

    sped_participante_id = fields.Many2one(
        comodel_name='sped.participante',
        string='Participante',
        ondelete='cascade',
    )
    sped_empresa_id = fields.Many2one(
        comodel_name='sped.empresa',
        string='Empresa',
    )
    is_brazilian = fields.Boolean(
        string='Is a Brazilian partner?',
        compute='_compute_is_brazilian',
        store=True,
    )
    original_company_id = fields.Many2one(
        comodel_name='res.company',
        string='Original Company',
        compute='_compute_original_company_id',
        store=True,
        ondelete='cascade',
    )
    original_user_id = fields.Many2one(
        comodel_name='res.users',
        string='Original User',
        compute='_compute_original_user_id',
        store=True,
        ondelete='cascade',
    )

    # campos do core do modo account override para nao ser required
    property_account_payable_id = fields.Many2one(
        comodel_name='account.account',
        required=False,
    )
    property_account_receivable_id = fields.Many2one(
        comodel_name='account.account',
        required=False,
    )

    name = fields.Char(
        string='Tag Name',
        required=False,
    )

    @api.depends('sped_participante_id')
    def _compute_is_brazilian(self):
        for partner in self:
            partner.is_brazilian = partner.sped_participante_id

    def _compute_original_company_id(self):
        for partner in self:
            company_ids = self.env['res.company'].search(
                [('partner_id', '=', partner.id)])

            if len(company_ids) > 0:
                partner.original_company_id = company_ids[0]
            else:
                partner.original_company_id = False

    def _compute_original_user_id(self):
        for partner in self:
            user_ids = self.env['res.users'].search(
                [('partner_id', '=', partner.id)])

            if len(user_ids) > 0:
                partner.original_user_id = user_ids[0]
            else:
                partner.original_user_id = False

    @api.model
    def create(self, vals):
        partner = super(ResPartner, self).create(vals)
        if "create_sped_participante" not in self._context:
            partner.with_context(
                create_from_partner=True).create_participante_id()
        return partner
    
    @api.multi
    def create_participante_id(self):
        Participante = self.env["sped.participante"]
        for partner_id in self.with_context(active_test=False):
            new_participante = Participante.create({
                'partner_id': partner_id.id,
            })
        return True
