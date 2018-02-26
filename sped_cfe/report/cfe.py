# -*- coding: utf-8 -*-
# Copyright 2018 KMEE
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from __future__ import division, print_function, unicode_literals

import logging
from odoo import api, models
from odoo.addons.report_py3o.models.py3o_report import py3o_report_extender

_logger = logging.getLogger(__name__)

try:
    from satcomum.ersat import ChaveCFeSAT, meio_pagamento
except (ImportError, IOError) as err:
    _logger.debug(err)


@api.model
@py3o_report_extender('sped_cfe.action_report_sped_documento_cfe')
def report_sped_documento_cfe(session, local_context):
    data = {
        'ChaveCFeSAT': ChaveCFeSAT,
        'meio_pagamento': meio_pagamento,
    }
    local_context.update(data)


class IrActionsReportXml(models.Model):
    _inherit = 'ir.actions.report.xml'

    @api.model
    def render_report(self, res_ids, name, data):
        action_py3o_report = self.get_from_report_name(name, "py3o")
        if action_py3o_report:
            document, file_type = self.env['py3o.report'].create({
                'ir_actions_report_xml_id': action_py3o_report.id
            }).create_report(res_ids, data)
            if name != 'report_sped_documento_cfe':
                return document, file_type
            report = self.search([('report_name', '=', name)], limit=1)
            behaviour = report.behaviour()[report.id]
            printer = behaviour['printer']

            can_print_report = self._can_print_report(
                behaviour, printer, document)

            if can_print_report:
                printer.print_document(report, document, report.report_type)
                return
            return document, file_type
        return super(IrActionsReportXml, self).render_report(
            res_ids, name, data)
