# -*- coding: utf-8 -*-
# Copyright (C) 2012 - TODAY  Renato Lima - Akretion
# Copyright 2018 KMEE INFORMATICA LTDA
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

import re

from odoo import models, fields, api
from odoo.addons.l10n_br_base.models.base_participante import (
    Participante,
    Pessoa,
)
from odoo.exceptions import ValidationError
from odoo.tools.translate import _


class CrmLead(Participante, Pessoa, models.Model):
    """ CRM Lead Case """
    _inherit = "crm.lead"

    @api.onchange('partner_id')
    def _onchange_partner_id(self):
        result = super(CrmLead, self)._onchange_partner_id_values(
            self.partner_id.id if self.partner_id else False
        )
        if self.partner_id:
            result['partner_name'] = self.partner_id.name
            result['razao_social'] = self.partner_id.razao_social
            result['fantasia'] = self.partner_id.fantasia
            result['cnpj_cpf'] = self.partner_id.cnpj_cpf
            result['ie'] = self.partner_id.ie
            result['suframa'] = self.partner_id.suframa
            result['numero'] = self.partner_id.numero
            result['bairro'] = self.partner_id.bairro
            result['municipio_id'] = \
                self.partner_id.municipio_id.id
        self.update(result)

    @api.model
    def _lead_create_contact(self, name, is_company,
                             parent_id=False, lead=False):
        """ extract data from lead to create a partner.
            Se passar um lead como parâmetro, extrair dados do parâmetro, senão
            extrair dados do self.
            :param name : furtur name of the partner
            :param is_company : True if the partner is a company
            :param lead : lead para extrair os dados
            :param parent_id : id of the parent partner (False if no parent)
            :returns res.partner record
        """
        partner_id = super(CrmLead, self)._lead_create_contact(
            name, is_company, parent_id)

        if not lead:
            lead = self[0]

        value = {
            'numero': lead.numero,
            'bairro': lead.bairro,
            'municipio_id': lead.municipio_id.id,
            'regime_tributario': lead.regime_tributario,
            'eh_consumidor_final': lead.eh_consumidor_final,
            'eh_transportadora': lead.eh_transportadora,
            'eh_orgao_publico': lead.eh_orgao_publico,
            'eh_funcionario': lead.eh_funcionario,
            'contribuinte': lead.contribuinte,
        }

        if is_company:
            value.update({
                'razao_social': lead.razao_social,
                'fantasia': lead.fantasia,
                'cnpj_cpf': lead.cnpj_cpf,
                'ie': lead.ie,
                'im': lead.im,
                'suframa': lead.suframa,
                'cei': lead.cei,
                'rntrc': lead.rntrc,
                'crc': lead.crc,
                'crc_uf': lead.crc_uf,
                'rg_numero': lead.rg_numero,
                'rg_orgao_emissor': lead.rg_orgao_emissor,
                'rg_data_expedicao': lead.rg_data_expedicao,
            })
        else:
            value.update({
                'razao_social': lead.nome,
                'cnpj_cpf': lead.cpf,
                'rg_numero': lead.rg,
            })

        if partner_id:
            partner_id.write(value)
        return partner_id
