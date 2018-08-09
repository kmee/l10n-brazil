# -*- coding: utf-8 -*-
# Copyright (C) 2016  Magno Costa - Akretion
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
from openerp import models, api
from openerp.addons.l10n_br_zip_correios.models.webservice_client\
    import WebServiceClient


class L10nBrZip(models.Model, WebServiceClient):

    _inherit = 'l10n_br.zip'

    @api.multi
    def zip_search_multi(self, country_id=False,
                         state_id=False, l10n_br_city_id=False,
                         district=False, street=False, zip_code=False):

        self.get_address(zip_code)
        return super(L10nBrZip, self).zip_search_multi(
            country_id, state_id, l10n_br_city_id, district, street, zip_code)

    @api.multi
    def zip_search_multi_json(self, country_id=False,
                         state_id=False, l10n_br_city_id=False,
                         district=False, street=False, zip_code=False):
        object = self.zip_search_multi(zip_code=zip_code)
        json = {'country_id': object.country_id.id, 'state_id': object.state_id.id,
                'l10n_br_city': object.l10n_br_city_id.id, 'district': object.district, 'street': object.street,
                'zip':object.zip}
        return json

