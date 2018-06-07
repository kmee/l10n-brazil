# -*- coding: utf-8 -*-
# Copyright (C) 2009  Renato Lima - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from openerp import models, fields, api


class L10nBrBaseCity(models.Model):
    """ Este objeto persite todos os municípios relacionado a um estado.
    No Brasil é necesário em alguns documentos fiscais informar o código
    do IBGE dos município envolvidos na transação.
    """
    _name = 'l10n_br_base.city'
    _description = u'Municipio'

    name = fields.Char('Nome', size=64, required=True)
    state_id = fields.Many2one('res.country.state', 'Estado', required=True)
    ibge_code = fields.Char(u'Código IBGE', size=7)

    @api.model
    def get_city_ids(self, id_state):
        state_ids = self.search([('state_id.id', '=', id_state)])
        dict = {}
        for id in state_ids._ids:
            dict[id] = self.browse(id).name
        return dict
