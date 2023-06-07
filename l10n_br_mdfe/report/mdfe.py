# Copyright 2018 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

import logging

from odoo import models
from odoo.addons.report_py3o.models.py3o_report import py3o_report_extender
from odoo.fields import Datetime

_logger = logging.getLogger(__name__)


def formata_data(doc, data):
    return Datetime.context_timestamp(doc, Datetime.from_string(data))


@py3o_report_extender('l10n_br_mdfe.action_report_sped_documento_mdfe')
def report_sped_documento_mdfe(session, local_context):
    data = {
        'formata_data': formata_data,
    }
    local_context.update(data)


class report_custom(models.AbstractModel):
    '''
        Custom report for return danfe
    '''

    _name = "report.l10n_br.mdfe"

    def _get_report_values(self, docids):
        records = self.env['l10n_br_fiscal.document'].browse(docids)
        return {
            'docs': records,
        }


report_custom._get_report_values('report_sped_documento_mdfe')
